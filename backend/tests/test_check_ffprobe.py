from pipeline.check_ffprobe import parse_probe_json, build_cmd


def test_parse_video_stream():
    j = '{"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080}]}'
    detail, h = parse_probe_json(j)
    assert h == 1080 and "h264" in detail and "1920x1080" in detail


def test_parse_audio_only():
    j = '{"streams":[{"codec_type":"audio","codec_name":"aac"}]}'
    detail, h = parse_probe_json(j)
    assert detail == "audio" and h == 0


def test_parse_no_streams():
    detail, h = parse_probe_json('{"streams":[]}')
    assert detail == "no-streams" and h == 0


def test_build_cmd_has_json_and_url():
    cmd = build_cmd("http://a/1.m3u8", 10)
    assert cmd[0] == "ffprobe"
    assert "-of" in cmd and "json" in cmd
    assert cmd[-1] == "http://a/1.m3u8"
