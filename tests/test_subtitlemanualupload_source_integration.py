from __future__ import annotations

import hashlib
import importlib
import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=['v2', 'v3'])
def modules(request, monkeypatch):
    from test_subtitlemanualupload_online import load_online_module
    load_online_module()
    sdk = types.ModuleType('app.sdk')
    monkeypatch.setitem(sys.modules, 'app.sdk', sdk)
    monkeypatch.setitem(sys.modules, 'app.sdk.config', sys.modules['app.core.config'])
    monkeypatch.setitem(sys.modules, 'app.sdk.logging', sys.modules['app.log'])
    package_name = f'source_integration_{request.param}'
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / f'plugins.{request.param}' / 'subtitlemanualupload')]
    monkeypatch.setitem(sys.modules, package_name, package)
    # Load the cache module without importing the host's unrelated SDK media service.
    auto_package = types.ModuleType(package_name + '.auto_transfer')
    auto_package.__path__ = [str(Path(package.__path__[0]) / 'auto_transfer')]
    monkeypatch.setitem(sys.modules, package_name + '.auto_transfer', auto_package)
    return lambda name: importlib.import_module(f'{package_name}.{name}')


def test_catalog_matches_service_configuration_and_capabilities(modules):
    catalog = modules('online_subtitles.catalog')
    service = modules('online_subtitles.service').OnlineSubtitleSearchService()
    schema = modules('config.config_schema')
    assert set(service.providers) == set(catalog.AVAILABLE_ONLINE_PROVIDER_IDS)
    assert set(service.manual_providers) == set(service.providers)
    assert 'zimuku' not in service.providers
    assert schema.DEFAULT_ONLINE_PROVIDER_IDS == ['subhd', 'subtitlecat']
    assert all(item['media_types'] == ['movie', 'tv'] for item in service.status()['providers'])
    assert 'secret' not in json.dumps(service.status())


@pytest.mark.parametrize('selected,expected', [([], []), (['zimuku'], []), (['zimuku', 'subhd'], ['subhd']), (['subdl', 'subtitlecat'], ['subdl', 'subtitlecat'])])
def test_explicit_selection_survives_keys_and_retired_source_migration(modules, selected, expected):
    schema = modules('config.config_schema')
    normalized = schema.normalize_plugin_config({
        'online_providers': selected,
        'subdl_api_key': 'secret', 'assrt_api_key': 'secret', 'opensubtitles_api_key': 'secret',
        'subtitlecat_include_translations': True,
    })
    assert normalized['online_providers'] == expected
    assert normalized['subdl_api_key'] == 'secret'
    assert normalized['subtitlecat_include_translations'] is True
    assert 'zimuku' not in normalized['online_site_urls']


def test_config_runtime_round_trip_preserves_new_settings(modules):
    schema = modules('config.config_schema')
    runtime = modules('config.config_runtime')
    owner = types.SimpleNamespace()
    config = schema.normalize_plugin_config({'online_providers': ['subtitlecat', 'subdl'], 'subdl_api_key': 'secret', 'subtitlecat_include_translations': True})
    runtime.apply_runtime_config(owner, config)
    saved = runtime.build_save_config_payload(owner)
    assert saved['online_providers'] == ['subtitlecat', 'subdl']
    assert saved['subdl_api_key'] == 'secret'
    assert saved['subtitlecat_include_translations'] is True
    assert 'zimuku_url' not in saved
    assert schema.normalize_plugin_config(saved)['online_providers'] == saved['online_providers']


def session(modules, tmp_path):
    upload = modules('upload.upload_session')
    return upload.UploadSessionService(
        data_path=tmp_path, subtitle_exts={'.srt', '.ass', '.smi'}, archive_exts={'.zip'}, rar_exts=set(), sevenzip_exts=set(),
        default_session_hours=1, hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        extract_rar_subtitle_files=None, extract_7z_subtitle_files=None,
    )


@pytest.mark.parametrize('content', [b'quota exhausted', b'<html><title>Error</title></html>', '字幕错误'.encode('utf-16'), b'1\n00:00:03,000 --> 00:00:02,000\nInvalid'])
@pytest.mark.parametrize('archived', [False, True])
def test_online_download_rejects_invalid_files_after_extraction(modules, tmp_path, content, archived):
    name = 'example.srt'
    if archived:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr(name, content)
        name, content = 'example.zip', stream.getvalue()
    with pytest.raises(ValueError):
        session(modules, tmp_path).extract_online_subtitle_files(name, content, tmp_path)


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16', 'gb18030'])
def test_online_srt_retains_valid_cues_and_encoding(modules, tmp_path, encoding):
    content = '1\n00:00:01,000 --> 00:00:02,000\n你好，世界\n'.encode(encoding)
    files = session(modules, tmp_path).extract_online_subtitle_files('example.srt', content, tmp_path)
    assert len(files) == 1
    assert Path(files[0]['stored_path']).read_bytes() == content


def test_webpage_sniffing_preserves_sami_and_distinguishes_result_ids(modules):
    shared = modules('online_subtitles.shared')
    assert shared._looks_like_html_bytes(b'<html><title>Error</title></html>', 'wrong.srt')
    assert not shared._looks_like_html_bytes(b'<SAMI><HEAD><TITLE>Subtitle</TITLE></HEAD>', 'valid.smi')
    assert shared._stable_result_id('source', 'https://example.org/1') != shared._stable_result_id('source', 'https://example.org/2')


def test_frontend_and_python_consume_same_source_catalog():
    for version in ('v2', 'v3'):
        base = ROOT / f'plugins.{version}' / 'subtitlemanualupload'
        ui = (base / 'src/utils/onlineResult.js').read_text(encoding='utf-8')
        config = (base / 'src/components/Config.vue').read_text(encoding='utf-8')
        state = (base / 'src/composables/useOnlineSubtitles.js').read_text(encoding='utf-8')
        assert '../../online_subtitles/provider_catalog.json' in ui
        assert "from '../utils/onlineResult'" in config
        assert "configured.push(" not in state
        assert 'zimuku' not in ui + config + state


@pytest.mark.parametrize('valid', [False, True])
def test_cached_online_subtitles_are_revalidated_before_write(modules, tmp_path, valid):
    source = tmp_path / 'cache.srt'
    source.write_bytes(b'1\n00:00:01,000 --> 00:00:02,000\nHello' if valid else b'upstream error')
    cached = {'key': 'test', 'items': [{'stored_path': str(source), 'source_name': 'cache.srt'}]}
    calls = []
    owner = types.SimpleNamespace(_hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(), services=types.SimpleNamespace(upload_session=lambda: types.SimpleNamespace(get_session_root=lambda: tmp_path)))
    collaborators = types.SimpleNamespace(load_cache=lambda entry: cached, write_prepared_uploads_for_entries=lambda **kwargs: calls.append(kwargs) or {'status': 'written'})
    cache = modules('auto_transfer.auto_transfer_season').AutoTransferSeasonCache(owner, logger=None, collaborators=collaborators)
    if valid:
        assert cache.write_from_cache([{'id': 'one'}])['from_cache'] is True
        assert len(calls) == 1
    else:
        with pytest.raises(ValueError):
            cache.write_from_cache([{'id': 'one'}])
        assert not calls
