# (name, url, type)
#
# CCTV5 audit, 2026-09-18. Measured through the real pipeline with the shipped
# filter config (min_resolution=1280x720, min_speed=0.5, urls_limit=5). The
# ranges are 3 repeats on the same cached playlists, since single ffprobe
# readings are noisy enough to flip a stream in or out of the output:
#
#                          before    after
#   playable CCTV5 pool    12-13  ->  26-27
#   CCTV5 rows in output    2-2   ->   5-5
#   CCTV5+ rows in output   2-3   ->   4-5
#
# The pool gain is structural (genuinely new unique URLs) and holds every run.
# The output row counts vary by one because they depend on stream liveness at
# that instant, so treat them as expected ranges, not fixed numbers.
#
# Full pipeline run over all 12 seeds (cached playlists), attributing final rows
# to the source that won each URL under first-wins dedup. 6805 unique URLs ->
# 2547 after HTTP -> 1901 after ffprobe -> 806 final rows / 525 channel names:
#
#   source                owned  rows  chans  c5rows(*)
#   ccsh-live              1623   290    189     4
#   guovin-gd-result-m3u   1517   163    134     1
#   suxuang-ipv4           1044   107    105     0
#   vbskycn-iptv4           224   106    106     0
#   as-d-master            1718    60     48     1
#   bestfan-cn-all          152    49     39     4
#   iptv-org-cn             144    11     11     0
#   kimentanm-aptv           59    11     11     0
#   as-d-ipv4                42     8      6     0
#   yuechan-global           68     1      1     0
#   yang-gather             124     0      0     0
#   yuechan-iptv             90     0      0     0
#
# (*) c5rows is one run, so it reads lower than the ranges in the inline notes
# below: this run caught 10 CCTV5/CCTV5+ rows total, the 3-run range is 9-10.
# The owned/rows/chans columns are structural enough to compare sources directly.
#
# Read this before dropping a seed on volume grounds. as-d-master owns the most
# URLs yet converts worst (1718 -> 60), while bestfan-cn-all owns few but is a
# top CCTV5 contributor. yang-gather and yuechan-iptv contribute 0 rows but are
# still enabled=1, see the inline note on them for why they are kept anyway.
#
# Candidates were selected by marginal CCTV5 gain after first-wins dedup, not by
# raw playable count, which is misleading: a source that only re-lists URLs an
# earlier seed already owns adds no CCTV5 while still costing fetch, HTTP and
# ffprobe time. On that basis gohkh-ipv4, bestfan-cn-cctv, bestfan-cctv-status,
# guovin-gd-ipv4, guovin-gd-txt and ccsh-others were rejected as CCTV5-redundant.
# suxuang-ipv4 is likewise CCTV5-redundant (7 unique URLs, 0 playable) but is
# kept because it still contributes 105 non-CCTV5 channels to the playlist.
# Two pre-existing duplicate feeds were dropped entirely, see inline notes.
SEED_SOURCES = [
    ("iptv-org-cn", "https://iptv-org.github.io/iptv/countries/cn.m3u", "m3u"),
    ("guovin-gd-result-m3u",
     "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", "m3u"),
    # result.txt is NOT also seeded: on 2026-09-18 it parsed to the identical
    # 1618 entries / 1554 unique URLs / same channel names as result.m3u above,
    # so after first-wins dedup it owned 0 URLs and contributed nothing while
    # still costing a fetch plus its share of the HTTP and ffprobe budget.
    ("yang-gather", "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u", "m3u"),
    # Migu.m3u is NOT also seeded: all 42 of its entries duplicate Gather.m3u
    # (0 URLs owned after dedup) and it carries the same EPG URL, so it added
    # nothing. Its channels are a subset of Gather.m3u's 124.
    # Both fetch fine but contribute 0 rows to output, so they are left enabled
    # rather than deleted: Gather.m3u is 0/8 playable on 2026-09-18 (hosts
    # cdn-3.ttvb.eu.org and gslbserv.itv.cmvideo.cn gone) and IPTV.m3u is pure
    # rtp:// multicast, which only resolves on an IPTV set-top-box network, not
    # from a normal uplink. Keep them only if you expect either to come back.
    ("suxuang-ipv4",
     "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u", "m3u"),
    ("yuechan-iptv", "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u", "m3u"),
    ("yuechan-global", "https://raw.githubusercontent.com/YueChan/Live/main/Global.m3u", "m3u"),
    ("vbskycn-iptv4", "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u", "m3u"),
    ("kimentanm-aptv", "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u", "m3u"),
    ("as-d-ipv4",
     "https://raw.githubusercontent.com/AS-D/iptv-api/master/output/ipv4/result.m3u", "m3u"),
    ("bestfan-cn-all",
     "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8", "m3u"),
    # Verified 2026-09-18 by a full pipeline run over all 12 seeds (cached
    # playlists, shipped filter config), counting rows attributed to the URLs
    # this source won under first-wins dedup:
    #   1623 owned URLs, 290 final rows, 189 distinct channel names
    # That makes it the largest contributor to full.m3u by row count, and the
    # biggest single CCTV5 source. Per-run CCTV5/CCTV5+ attribution over 3 runs:
    #   ccsh-live 3-5 rows, bestfan-cn-all 3-4, guovin-gd-result-m3u 1-2,
    #   as-d-master 1
    # So bestfan (pre-existing) is nearly as important for CCTV5. Do not drop it
    # on the assumption that ccsh-live replaced it.
    ("ccsh-live", "https://raw.githubusercontent.com/CCSH/IPTV/main/live.m3u", "m3u"),
    # Verified 2026-09-18. Same full run as above: 1718 owned URLs (the most of
    # any seed, edging out ccsh-live's 1623) but only 60 final rows / 48 distinct
    # channel names, so it converts far worse than ccsh-live. It is kept for the
    # CCTV5 CDN URL below plus those ~48 channels, not for volume.
    # Uniquely owns playable CCTV5 on ldcctvwbcdks.v.kcdnvip.com, a domain-based
    # HTTPS CDN. Every other CCTV5 stream is a bare IP that rots, so this one
    # survives IP churn. Whether it reaches output is run-dependent. The feed has
    # two variants and ffprobe speed is probesize/elapsed, so it reflects shared
    # bandwidth at that instant:
    #   ?b=200-2100             ~0.25 MB/s, always fails filter.min_speed=0.5
    #   ?BR=td&region=shanghai  ~0.9 MB/s normally, but intermittently dips to
    #                           ~0.16 (2 of 12 probes under realistic mixed
    #                           traffic). That intermittency is why it scored
    #                           0.889 in one full run and was filtered in another.
    # (yuechan-global, by contrast, is genuinely slow: median 0.20 at both
    # workers=25 and workers=3, so that one is not a load artefact.)
    ("as-d-master",
     "https://raw.githubusercontent.com/AS-D/iptv-api/master/output/result.m3u", "m3u"),
    # Verified 2026-10-09: all 40 URLs (single hotel IPTV host 101.66.199.13:9901)
    # returned HTTP 200 with genuine #EXTM3U + .ts live bodies. TVBox txt format
    # (#genre# groups), parsed by parse_txt. Small and heavily overlapping with
    # the bigger seeds (CCTV1-15 + provincial satellites), so expect near-zero
    # owned URLs after first-wins dedup — kept as a redundancy source: if the
    # major seeds rot, this single-host feed is an independent fallback.
    # The repo's udpxy/ multicast files are NOT seeded: user's network is not on
    # an IPTV multicast VLAN (verified 2026-10-09, zero 239.77.x.x packets).
    ("ssili126-tv",
     "https://raw.githubusercontent.com/ssili126/tv/main/itvlist.txt", "txt"),
]

# (canonical, pattern, is_regex)
SEED_ALIASES = [
    ("CCTV1", r"^CCTV[-\s]?1(\s|综合|$)", 1),
    ("CCTV2", r"^CCTV[-\s]?2(\s|财经|$)", 1),
    ("CCTV5", r"^CCTV[-\s]?5(\s|体育|$)", 1),
    ("CCTV5+", r"^CCTV[-\s]?5\+(\s|体育赛事|$)", 1),
    ("CCTV13", r"^CCTV[-\s]?13(\s|新闻|$)", 1),
    ("湖南卫视", r"湖南卫视", 0),
    ("浙江卫视", r"浙江卫视", 0),
    ("东方卫视", r"东方卫视", 0),
    ("江苏卫视", r"江苏卫视", 0),
    ("北京卫视", r"北京卫视", 0),
]
