# requires urllib, requests, ffmpeg executables

CACHE = True
PAGE_URL = 'https://www.reddit.com/r/leagueoflegends/comments/itx93a/chinese_fiora_king_01_second_4_vitals/'  # https://www.reddit.com/r/Subreddit/comments/asdf123/funnycatvideo
OUTPUT = 'mp4'

import urllib
from pathlib import Path
import re, subprocess, shutil, os, sys, requests, json

re_m3u8 = r'(HLS\w+\.m3u8)'
re_reddit_src = r'v\.redd\.it\/(\w+)\/HLSPlaylist\.m3u8'
re_vid_name = r'https:.*\/\w+\/(\w+)'

re_ts = r'(HLS\w+\.(ts|aac))'
re_vid_ts = r'HLS_(\d+)[_MK]*\.(ts)'
re_audio_ts = r'\w+AUDIO_(\d+)_K\.(aac)'

# optional script args (overrides constants above)
if len(sys.argv) >= 2:
    PAGE_URL = sys.argv[1]
if len(sys.argv) >= 3:
    OUTPUT = sys.argv[2]


def rel_path(*p):
    return os.path.join(os.path.dirname(__file__), *p)


if len(PAGE_URL) == 0:
    exit('Error: Needs a page url')

if not os.path.exists(rel_path('ffmpeg.exe')):
    exit(f"Error: ffmpeg.exe not found at {rel_path('ffmpeg.exe')}")


# unused atm. used when reddit json was easily accessible
def find_url(d):
    if isinstance(d, list):
        for child in d:
            ret = find_url(child)
            if ret: return ret
    elif isinstance(d, dict):
        for k, v in d.items():
            ret = find_url(v)
            if ret: return ret
    elif isinstance(d, str):
        if d.endswith('.m3u8'):
            return d


def find_url_text(d):
    hash_result = re.search(re_reddit_src, str(d))
    print(f"found {hash_result.group()}")
    return hash_result.group()


# parse the url of the m3u8 playlist
m3u8_url = ''
with open('./cache.txt', 'a+') as f:
    page_data = None
    cache = {}
    f.seek(0)
    str_cache = f.read()
    if len(str_cache) > 2:
        cache = json.loads(str_cache)

    if CACHE and PAGE_URL in cache:
        page_data = cache[PAGE_URL]
    else:
        req = requests.get(PAGE_URL + '.json',
                           stream=True,
                           headers={'User-agent': 'notabot'})

        if req.content:
            page_data = None
            page_data = find_url_text(req.content)
            # find_url(json.loads(req.content))

            print(page_data)
        else:
            exit()

    if not page_data:
        print("No page data for thread url!")
        exit()

    f.seek(0)
    cache[PAGE_URL] = page_data
    f.truncate(0)
    json.dump(cache, f)

    m3u8_url = page_data

# parse the name of the reddit post
vid_name = 'output'
vid_hash = ''
name_result = re.search(re_vid_name, PAGE_URL)
if name_result:
    vid_name = name_result.group(1)

# parse the id of the reddit post's m3u8 file
hash_result = re.search(re_reddit_src, m3u8_url)
if hash_result:
    vid_hash = hash_result.group(1)


# used to download m3u8 and ts files of the reddit post
def get_file(f):
    print('download', f)
    Path(rel_path("files")).mkdir(parents=True, exist_ok=True)

    url = 'https://v.redd.it/' + vid_hash + '/' + f
    urllib.request.urlretrieve(url, rel_path('files', f))


get_file('HLSPlaylist.m3u8')

# download other m3u8
other_files = []
with open(rel_path("files", "HLSPlaylist.m3u8"), 'r') as f:
    lines = f.readlines()
    for l in lines:
        result = re.search(re_m3u8, l)
        if result:
            other_files.append(result.group(1))

# download ts files found in m3u8 files
ts_files = []
highest_vid = 0
highest_aud = 0
highest_vid_f = None
highest_aud_f = None
for other in other_files:
    get_file(other)
    with open(rel_path('files', other), 'r') as f:
        lines = f.readlines()
        for l in lines:
            result = re.search(re_ts, l)
            if result:
                f_name = result.group(1)
                ts_files.append(f_name)

                res_vid = re.search(re_vid_ts, f_name)
                if res_vid:
                    num = int(res_vid.group(1))
                    if num > highest_vid:
                        highest_vid_f = f_name
                        highest_vid = num
                res_aud = re.search(re_audio_ts, f_name)
                if res_aud:
                    num = int(res_aud.group(1))
                    if num > highest_aud:
                        highest_aud_f = f_name
                        highest_aud = num


def run_ffmpeg(cmd):
    cmd = f"{rel_path('ffmpeg')} {cmd}"
    print(cmd)
    subprocess.run(cmd)


print('Audio: ' + str(highest_aud_f) + ', Video: ' + str(highest_vid_f))

mkv_path = rel_path('output.mkv')
output_path = rel_path('output', vid_name + '.' + OUTPUT)

if highest_vid_f:
    Path(rel_path("output")).mkdir(parents=True, exist_ok=True)

    get_file(highest_vid_f)

    # no audio cmd
    cmd = f"-i {rel_path('files', highest_vid_f)} -map 0 -c copy {mkv_path}"

    # audio + video cmd
    if highest_aud_f:
        get_file(highest_aud_f)
        cmd = f"-y -i {rel_path('files',highest_aud_f)} -r 30 -i {rel_path('files',highest_vid_f)} -filter:a aresample=async=1 -c:a flac -c:v copy {mkv_path} -crf 20"

    run_ffmpeg(cmd)

    # convert mkv to OUTPUT format
    run_ffmpeg(f"-y -i {mkv_path} -crf 20 {output_path}")

# clean up m3u8, ts, and aac files
if os.path.exists(mkv_path):
    os.remove(mkv_path)
if os.path.exists(rel_path('files')):
    shutil.rmtree(rel_path('files'))
