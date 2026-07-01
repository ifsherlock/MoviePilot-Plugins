import iso639

from ..core.models import ResolvedSource


class SourceResolver:
    @staticmethod
    def get_video_prefer_audio(video_meta, prefer_lang=None, logger=None):
        if type(prefer_lang) == str and prefer_lang:
            prefer_lang = [prefer_lang]

        audio_lang = None
        audio_index = None
        audio_stream = filter(lambda x: x.get('codec_type') == 'audio', video_meta.get('streams', []))
        for index, stream in enumerate(audio_stream):
            if audio_index is None:
                audio_index = index
                audio_lang = stream.get('tags', {}).get('language', 'und')
            if stream.get('disposition', {}).get('default'):
                audio_index = index
                audio_lang = stream.get('tags', {}).get('language', 'und')
            if prefer_lang and stream.get('tags', {}).get('language') in prefer_lang:
                audio_index = index
                audio_lang = stream.get('tags', {}).get('language', 'und')
                break

        if audio_index is None:
            if logger:
                logger.warn("没有音轨，不进行处理")
            return False, None, None

        if logger:
            logger.info(f"选中音轨信息：{audio_index}, {audio_lang}")
        return True, audio_index, audio_lang

    @staticmethod
    def get_video_prefer_subtitle(video_meta, prefer_lang=None, strict=False, only_srt=True, logger=None):
        image_based_subtitle_codecs = (
            'dvd_subtitle',
            'dvb_subtitle',
            'hdmv_pgs_subtitle',
        )

        if prefer_lang is str and prefer_lang:
            prefer_lang = [prefer_lang]

        subtitle_lang = None
        subtitle_index = None
        subtitle_score = 0
        subtitle_stream = filter(lambda x: x.get('codec_type') == 'subtitle', video_meta.get('streams', []))
        for index, stream in enumerate(subtitle_stream):
            if stream.get('disposition', {}).get('forced'):
                continue
            if only_srt and (
                    'width' in stream
                    or stream.get('codec_name') in image_based_subtitle_codecs
            ):
                continue
            cur_is_default = stream.get('disposition', {}).get('default')
            cur_lang = stream.get('tags', {}).get('language')
            cur_score = 0
            if prefer_lang and cur_lang in prefer_lang:
                cur_score += 4
            if cur_is_default:
                cur_score += 2
            if subtitle_index is None:
                cur_score += 1
                subtitle_lang, subtitle_index, subtitle_score = cur_lang, index, cur_score
            if cur_score > subtitle_score:
                subtitle_lang, subtitle_index, subtitle_score = cur_lang, index, cur_score

        if subtitle_index is None:
            if logger:
                logger.debug("没有内嵌字幕")
            return False, None, None
        if strict and prefer_lang and subtitle_lang not in prefer_lang:
            if logger:
                logger.warn("严格模式,没有偏好语言的字幕")
            return False, None, None
        if logger:
            logger.debug(f"命中内嵌字幕信息：{subtitle_index}, {subtitle_lang}, score:{subtitle_score}")
        return True, subtitle_index, subtitle_lang

    @staticmethod
    def extract_embedded_subtitle(
        video_file,
        subtitle_file,
        subtitle_index,
        subtitle_lang,
        ffmpeg_factory,
        logger=None,
    ):
        subtitle_lang = iso639.to_iso639_1(subtitle_lang) \
            if (subtitle_lang and iso639.find(subtitle_lang) and iso639.to_iso639_1(subtitle_lang)) else 'und'
        extracted_sub_path = f"{subtitle_file}.{subtitle_lang}.srt"
        ffmpeg_factory().extract_subtitle_from_video(video_file, extracted_sub_path, subtitle_index)
        if logger:
            logger.info(f"提取字幕完成：{extracted_sub_path}")
        return True, subtitle_lang, (extracted_sub_path, ResolvedSource.EMBEDDED.value)
