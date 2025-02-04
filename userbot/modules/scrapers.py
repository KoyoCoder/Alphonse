#
""" Userbot module containing various scrapers. """

import json
import os
import re
import shutil
import time
from asyncio import get_event_loop, sleep
from glob import glob
from urllib.parse import quote_plus

import asyncurban
from bs4 import BeautifulSoup
from emoji import get_emoji_regexp
from googletrans import LANGUAGES, Translator
from gtts import gTTS
from gtts.lang import tts_langs
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from requests import get
from search_engine_parser import GoogleSearch
from telethon.errors.rpcerrorlist import MediaEmptyError
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from wikipedia import summary
from wikipedia.exceptions import DisambiguationError, PageError
from youtube_dl import YoutubeDL
from youtube_dl.utils import (
    ContentTooShortError,
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    MaxDownloadsReached,
    PostProcessingError,
    UnavailableVideoError,
    XAttrMetadataError,
)
from youtube_search import YoutubeSearch

from userbot import BOTLOG, BOTLOG_CHATID, CMD_HELP, TEMP_DOWNLOAD_DIRECTORY
from userbot.events import register
from userbot.modules.upload_download import get_video_thumb
from userbot.utils import chrome, googleimagesdownload, progress
from userbot.utils.FastTelethon import upload_file

CARBONLANG = "auto"


@register(outgoing=True, pattern=r"^\.crblang (.*)")
async def setlang(prog):
    global CARBONLANG
    CARBONLANG = prog.pattern_match.group(1)
    await prog.edit(f"Language for carbon.now.sh set to {CARBONLANG}")


@register(outgoing=True, pattern=r"^\.carbon")
async def carbon_api(e):
    """A Wrapper for carbon.now.sh"""
    await e.edit("**Processing...**")
    CARBON = "https://carbon.now.sh/?l={lang}&code={code}"
    global CARBONLANG
    textx = await e.get_reply_message()
    pcode = e.text
    if pcode[8:]:
        pcode = str(pcode[8:])
    elif textx:
        pcode = str(textx.message)  # Importing message to module
    code = quote_plus(pcode)  # Converting to urlencoded
    await e.edit("**Processing...\n25%**")
    dl_path = "./.carbon/"
    file_path = dl_path + "carbon.png"
    if os.path.isfile(file_path):
        os.remove(file_path)
    url = CARBON.format(code=code, lang=CARBONLANG)
    driver = await chrome()
    driver.get(url)
    await e.edit("**Processing...\n50%**")
    driver.command_executor._commands["send_command"] = (
        "POST",
        "/session/$sessionId/chromium/send_command",
    )
    params = {
        "cmd": "Page.setDownloadBehavior",
        "params": {"behavior": "allow", "downloadPath": dl_path},
    }
    driver.execute("send_command", params)
    driver.find_element_by_css_selector('[data-cy="quick-export-button"]').click()
    await e.edit("**Processing...\n75%**")
    # Waiting for downloading
    while not os.path.isfile(file_path):
        await sleep(0.5)
    await e.edit("**Processing...\n100%**")
    await e.edit("**Uploading...**")
    await e.client.send_file(
        e.chat_id,
        file_path,
        caption=(
            "Made using [Carbon](https://carbon.now.sh/about/),"
            "\na project by [Dawn Labs](https://dawnlabs.io/)"
        ),
        force_document=True,
        reply_to=e.message.reply_to_msg_id,
    )

    os.remove(file_path)
    driver.quit()
    # Removing carbon.png after uploading
    await e.delete()  # Deleting msg


@register(outgoing=True, pattern=r"^\.img(?: |$)(\d*)? ?(.*)")
async def img_sampler(event):
    """For .img command, search and return images matching the query."""

    if event.is_reply and not event.pattern_match.group(2):
        query = await event.get_reply_message()
        query = str(query.message)
    else:
        query = str(event.pattern_match.group(2))

    if not query:
        return await event.edit("**Reply to a message or pass a query to search!**")

    await event.edit("**Processing...**")

    if event.pattern_match.group(1) != "":
        counter = int(event.pattern_match.group(1))
        if counter > 10:
            counter = int(10)
        if counter <= 0:
            counter = int(1)
    else:
        counter = int(3)

    response = googleimagesdownload()

    # creating list of arguments
    arguments = {
        "keywords": query,
        "limit": counter,
        "format": "png",
        "no_directory": "no_directory",
    }

    # if the query contains some special characters, googleimagesdownload errors out
    # this is a temporary workaround for it (maybe permanent)
    try:
        paths = response.download(arguments)
    except Exception as e:
        return await event.edit(f"**Error:** `{e}`")

    lst = paths[0][query.replace(",", " ")]
    try:
        await event.client.send_file(event.chat_id, lst)
    except MediaEmptyError:
        for i in lst:
            try:
                await event.client.send_file(event.chat_id, i)
            except MediaEmptyError:
                pass
    shutil.rmtree(os.path.dirname(os.path.abspath(lst[0])))
    await event.delete()


@register(outgoing=True, pattern=r"^\.currency ([\d\.]+) ([a-zA-Z]+) ([a-zA-Z]+)")
async def moni(event):
    c_from_val = float(event.pattern_match.group(1))
    c_from = (event.pattern_match.group(2)).upper()
    c_to = (event.pattern_match.group(3)).upper()
    try:
        response = get(
            "https://api.frankfurter.app/latest",
            params={"from": c_from, "to": c_to},
        ).json()
    except Exception:
        await event.edit("**Error: API is down.**")
        return
    if "error" in response:
        await event.edit(
            "**This seems to be some alien currency, which I can't convert right now.**"
        )
        return
    c_to_val = round(c_from_val * response["rates"][c_to], 2)
    await event.edit(f"**{c_from_val} {c_from} = {c_to_val} {c_to}**")


@register(outgoing=True, pattern=r"^\.google(?: |$)(\d*)? ?(.*)")
async def gsearch(event):
    """For .google command, do a Google search."""

    if event.is_reply and not event.pattern_match.group(2):
        match = await event.get_reply_message()
        match = str(match.message)
    else:
        match = str(event.pattern_match.group(2))

    if not match:
        return await event.edit("**Reply to a message or pass a query to search!**")

    await event.edit("**Processing...**")

    if event.pattern_match.group(1) != "":
        counter = int(event.pattern_match.group(1))
        if counter > 10:
            counter = int(10)
        if counter <= 0:
            counter = int(1)
    else:
        counter = int(3)

    search_args = (str(match), int(1))
    gsearch = GoogleSearch()

    try:
        gresults = await gsearch.async_search(*search_args)
    except Exception:
        return await event.edit(
            "**Error: Your query could not be found or it was flagged as unusual traffic.**"
        )
    msg = ""

    for i in range(counter):
        try:
            title = gresults["titles"][i]
            link = gresults["links"][i]
            desc = gresults["descriptions"][i]
            msg += f"[{title}]({link})\n`{desc}`\n\n"
        except IndexError:
            break

    await event.edit(
        "**Search Query:**\n`" + match + "`\n\n**Results:**\n" + msg, link_preview=False
    )


@register(outgoing=True, pattern=r"^\.wiki(?: |$)(.*)")
async def wiki(wiki_q):
    """For .wiki command, fetch content from Wikipedia."""

    if wiki_q.is_reply and not wiki_q.pattern_match.group(1):
        match = await wiki_q.get_reply_message()
        match = str(match.message)
    else:
        match = str(wiki_q.pattern_match.group(1))

    if not match:
        return await wiki_q.edit("**Reply to a message or pass a query to search!**")

    await wiki_q.edit("**Processing...**")

    try:
        summary(match)
    except DisambiguationError as error:
        return await wiki_q.edit(f"**Disambiguated page found.**\n\n`{error}`")
    except PageError as pageerror:
        return await wiki_q.edit(f"**Page not found.**\n\n`{pageerror}`")
    result = summary(match)
    if len(result) >= 4096:
        with open("output.txt", "w+") as file:
            file.write(result)
        await wiki_q.client.send_file(
            wiki_q.chat_id,
            "output.txt",
            reply_to=wiki_q.id,
            caption=r"**Output too large, sending as file**",
        )
        if os.path.exists("output.txt"):
            return os.remove("output.txt")
    await wiki_q.edit("**Search:**\n`" + match + "`\n\n**Result:**\n" + result)


@register(outgoing=True, pattern=r"^\.ud(?: |$)(.*)")
async def urban_dict(event):
    """Output the definition of a word from Urban Dictionary"""

    if event.is_reply and not event.pattern_match.group(1):
        query = await event.get_reply_message()
        query = str(query.message)
    else:
        query = str(event.pattern_match.group(1))

    if not query:
        return await event.edit("**Reply to a message or pass a query to search!**")

    await event.edit("**Processing...**")
    ud = asyncurban.UrbanDictionary()
    template = "**Query:** `{}`\n\n**Definition:**\n{}\n\n**Example:**\n__{}__"

    try:
        definition = await ud.get_word(query)
    except asyncurban.UrbanException as e:
        return await event.edit(f"**Error:** `{e}`")

    result = template.format(definition.word, definition.definition, definition.example)

    if len(result) < 4096:
        return await event.edit(result)

    await event.edit("**Output too large, sending as file...**")
    with open("output.txt", "w+") as file:
        file.write(
            "Query: "
            + definition.word
            + "\n\nMeaning: "
            + definition.definition
            + "Example: \n"
            + definition.example
        )
    await event.client.send_file(
        event.chat_id,
        "output.txt",
        caption=f"Urban Dictionary's definition of {query}",
    )
    if os.path.exists("output.txt"):
        os.remove("output.txt")
    return await event.delete()


@register(outgoing=True, pattern=r"^\.tts(?: |$)([\s\S]*)")
async def text_to_speech(query):
    """For .tts command, a wrapper for Google Text-to-Speech."""

    if query.is_reply and not query.pattern_match.group(1):
        message = await query.get_reply_message()
        message = str(message.message)
    else:
        message = str(query.pattern_match.group(1))

    if not message:
        return await query.edit(
            "**Give a text or reply to a message for Text-to-Speech!**"
        )

    await query.edit("**Processing...**")

    try:
        from userbot.modules.sql_helper.globals import gvarstatus
    except AttributeError:
        return await query.edit("**Running on Non-SQL mode!**")

    if gvarstatus("tts_lang") is not None:
        target_lang = str(gvarstatus("tts_lang"))
    else:
        target_lang = "en"

    try:
        gTTS(message, lang=target_lang)
    except AssertionError:
        return await query.edit(
            "**The text is empty.**\n"
            "Nothing left to speak after pre-precessing, tokenizing and cleaning."
        )
    except ValueError:
        return await query.edit("**Language is not supported.**")
    except RuntimeError:
        return await query.edit("**Error loading the languages dictionary.**")
    tts = gTTS(message, lang=target_lang)
    tts.save("k.mp3")
    with open("k.mp3", "rb") as audio:
        linelist = list(audio)
        linecount = len(linelist)
    if linecount == 1:
        tts = gTTS(message, lang=target_lang)
        tts.save("k.mp3")
    with open("k.mp3"):
        await query.client.send_file(query.chat_id, "k.mp3", voice_note=True)
        os.remove("k.mp3")
    await query.delete()


# kanged from Blank-x ;---;
@register(outgoing=True, pattern=r"^\.imdb (.*)")
async def imdb(e):
    try:
        movie_name = e.pattern_match.group(1)
        remove_space = movie_name.split(" ")
        final_name = "+".join(remove_space)
        page = get(
            "https://www.imdb.com/find?ref_=nv_sr_fn&q=r" + final_name + "&s=all"
        )
        soup = BeautifulSoup(page.content, "lxml")
        odds = soup.findAll("tr", "odd")
        mov_title = odds[0].findNext("td").findNext("td").text
        mov_link = (
            "http://www.imdb.com/" + odds[0].findNext("td").findNext("td").a["href"]
        )
        page1 = get(mov_link)
        soup = BeautifulSoup(page1.content, "lxml")
        if soup.find("div", "poster"):
            poster = soup.find("div", "poster").img["src"]
        else:
            poster = ""
        if soup.find("div", "title_wrapper"):
            pg = soup.find("div", "title_wrapper").findNext("div").text
            mov_details = re.sub(r"\s+", " ", pg)
        else:
            mov_details = ""
        credits = soup.findAll("div", "credit_summary_item")
        director = credits[0].a.text
        if len(credits) == 1:
            writer = "Not available"
            stars = "Not available"
        elif len(credits) > 2:
            writer = credits[1].a.text
            actors = [x.text for x in credits[2].findAll("a")]
            actors.pop()
            stars = actors[0] + "," + actors[1] + "," + actors[2]
        else:
            writer = "Not available"
            actors = [x.text for x in credits[1].findAll("a")]
            actors.pop()
            stars = actors[0] + "," + actors[1] + "," + actors[2]
        if soup.find("div", "inline canwrap"):
            story_line = soup.find("div", "inline canwrap").findAll("p")[0].text
        else:
            story_line = "Not available"
        info = soup.findAll("div", "txt-block")
        if info:
            mov_country = []
            mov_language = []
            for node in info:
                a = node.findAll("a")
                for i in a:
                    if "country_of_origin" in i["href"]:
                        mov_country.append(i.text)
                    elif "primary_language" in i["href"]:
                        mov_language.append(i.text)
        if soup.findAll("div", "ratingValue"):
            for r in soup.findAll("div", "ratingValue"):
                mov_rating = r.strong["title"]
        else:
            mov_rating = "Not available"
        await e.edit(
            "<a href=" + poster + ">&#8203;</a>"
            "<b>Title : </b><code>"
            + mov_title
            + "</code>\n<code>"
            + mov_details
            + "</code>\n<b>Rating : </b><code>"
            + mov_rating
            + "</code>\n<b>Country : </b><code>"
            + mov_country[0]
            + "</code>\n<b>Language : </b><code>"
            + mov_language[0]
            + "</code>\n<b>Director : </b><code>"
            + director
            + "</code>\n<b>Writer : </b><code>"
            + writer
            + "</code>\n<b>Stars : </b><code>"
            + stars
            + "</code>\n<b>IMDB Url : </b>"
            + mov_link
            + "\n<b>Story Line : </b>"
            + story_line,
            link_preview=True,
            parse_mode="HTML",
        )
    except IndexError:
        await e.edit("Plox enter **Valid movie name** kthx")


@register(outgoing=True, pattern=r"^\.trt(?: |$)([\s\S]*)")
async def translateme(trans):
    """For .trt command, translate the given text using Google Translate."""

    if trans.is_reply and not trans.pattern_match.group(1):
        message = await trans.get_reply_message()
        message = str(message.message)
    else:
        message = str(trans.pattern_match.group(1))

    if not message:
        return await trans.edit(
            "**Give some text or reply to a message to translate!**"
        )

    await trans.edit("**Processing...**")
    translator = Translator()

    try:
        from userbot.modules.sql_helper.globals import gvarstatus
    except AttributeError:
        return await trans.edit("**Running on Non-SQL mode!**")

    if gvarstatus("trt_lang") is not None:
        target_lang = str(gvarstatus("trt_lang"))
    else:
        target_lang = "en"

    try:
        reply_text = translator.translate(deEmojify(message), dest=target_lang)
    except ValueError:
        return await trans.edit(
            "**Invalid language selected, use **`.lang trt <language code>`**.**"
        )

    source_lang = LANGUAGES.get(reply_text.src).title()  # type: ignore
    target_lang = LANGUAGES.get(target_lang).title()

    reply_text = f"From: **{source_lang}**\nTo: **{target_lang}**\n\n{reply_text.text}"  # type: ignore

    await trans.edit(reply_text)


@register(pattern=r"\.lang (trt|tts) (.*)", outgoing=True)
async def lang(value):
    """For .lang command, change the default langauge of userbot scrapers."""
    util = value.pattern_match.group(1).lower()

    try:
        from userbot.modules.sql_helper.globals import addgvar, delgvar, gvarstatus
    except AttributeError:
        return await lang.edit("**Running on Non-SQL mode!**")

    if util == "trt":
        scraper = "Translator"
        arg = value.pattern_match.group(2).lower()

        if arg not in LANGUAGES:
            return await value.edit(
                f"**Invalid language code!**\nAvailable language codes:\n\n`{LANGUAGES}`"
            )

        if gvarstatus("trt_lang"):
            delgvar("trt_lang")
        addgvar("trt_lang", arg)
        LANG = LANGUAGES[arg]

    elif util == "tts":
        scraper = "Text to Speech"
        arg = value.pattern_match.group(2).lower()

        if arg not in tts_langs():
            return await value.edit(
                f"**Invalid language code!**\nAvailable language codes:\n\n`{tts_langs()}`"
            )

        if gvarstatus("tts_lang"):
            delgvar("tts_lang")
        addgvar("tts_lang", arg)
        LANG = tts_langs()[arg]

    await value.edit(f"**Language for {scraper} changed to {LANG.title()}.**")
    if BOTLOG:
        await value.client.send_message(
            BOTLOG_CHATID, f"`Language for {scraper} changed to {LANG.title()}.`"
        )


@register(outgoing=True, pattern=r"^\.yt(?: |$)(\d*)? ?(.*)")
async def yt_search(event):
    """For .yt command, do a YouTube search from Telegram."""

    if event.is_reply and not event.pattern_match.group(2):
        query = await event.get_reply_message()
        query = str(query.message)
    else:
        query = str(event.pattern_match.group(2))

    if not query:
        return await event.edit("**Reply to a message or pass a query to search!**")

    await event.edit("**Processing...**")

    if event.pattern_match.group(1) != "":
        counter = int(event.pattern_match.group(1))
        if counter > 10:
            counter = int(10)
        if counter <= 0:
            counter = int(1)
    else:
        counter = int(3)

    try:
        results = json.loads(YoutubeSearch(query, max_results=counter).to_json())
    except KeyError:
        return await event.edit("**YouTube gone retard.\nCan't search this query!**")

    output = f"**Search Query:**\n`{query}`\n\n**Results:**\n"

    for i in results["videos"]:
        try:
            title = i["title"]
            link = "https://youtube.com" + i["url_suffix"]
            channel = i["channel"]
            duration = i["duration"]
            views = i["views"]
            output += f"[{title}]({link})\nChannel: `{channel}`\nDuration: {duration} | {views}\n\n"
        except IndexError:
            break

    await event.edit(output, link_preview=False)


@register(outgoing=True, pattern=r"\.r(a|v( \d{0,4})?) (.*)")
async def download_video(v_url):
    """For .rip command, download media from YouTube and many other sites."""
    dl_type = v_url.pattern_match.group(1).lower()
    reso = v_url.pattern_match.group(2)
    reso = reso.strip() if reso else None
    url = v_url.pattern_match.group(3)

    await v_url.edit("**Preparing to download...**")
    s_time = time.time()
    video = False
    audio = False

    if "a" in dl_type:
        opts = {
            "format": "bestaudio",
            "addmetadata": True,
            "key": "FFmpegMetadata",
            "writethumbnail": True,
            "prefer_ffmpeg": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ],
            "outtmpl": os.path.join(
                TEMP_DOWNLOAD_DIRECTORY, str(s_time), "%(title)s.%(ext)s"
            ),
            "quiet": True,
            "logtostderr": False,
        }
        audio = True

    else:
        quality = (
            f"bestvideo[height<={reso}]+bestaudio/best[height<={reso}]"
            if reso
            else "bestvideo+bestaudio/best"
        )
        opts = {
            "format": quality,
            "addmetadata": True,
            "key": "FFmpegMetadata",
            "prefer_ffmpeg": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "outtmpl": os.path.join(
                TEMP_DOWNLOAD_DIRECTORY, str(s_time), "%(title)s.%(ext)s"
            ),
            "logtostderr": False,
            "quiet": True,
        }
        video = True

    try:
        await v_url.edit("**Fetching data, please wait...**")
        with YoutubeDL(opts) as rip:
            rip_data = rip.extract_info(url)
    except DownloadError as DE:
        return await v_url.edit(f"**{DE}**")
    except ContentTooShortError:
        return await v_url.edit("**The download content was too short.**")
    except GeoRestrictedError:
        return await v_url.edit(
            "**Video is not available from your geographic location "
            "due to geographic restrictions imposed by a website.**"
        )
    except MaxDownloadsReached:
        return await v_url.edit("**Max-downloads limit has been reached.**")
    except PostProcessingError:
        return await v_url.edit("**There was an error during post processing.**")
    except UnavailableVideoError:
        return await v_url.edit("**Media is not available in the requested format.**")
    except XAttrMetadataError as XAME:
        return await v_url.edit(f"**{XAME.code}: {XAME.msg}\n{XAME.reason}**")
    except ExtractorError:
        return await v_url.edit("**There was an error during info extraction.**")
    except Exception as e:
        return await v_url.edit(f"**{str(type(e)): {e}}**")
    c_time = time.time()
    if audio:
        await v_url.edit(
            f"**Preparing to upload song:**\n`{rip_data.get('title')}`"
            f"\nby `{rip_data.get('uploader')}`"
        )
        f_name = glob(os.path.join(TEMP_DOWNLOAD_DIRECTORY, str(s_time), "*.mp3"))[0]
        with open(f_name, "rb") as f:
            result = await upload_file(
                client=v_url.client,
                file=f,
                name=f_name,
                progress_callback=lambda d, t: get_event_loop().create_task(  # type: ignore
                    progress(
                        d,
                        t,
                        v_url,
                        c_time,
                        "**Uploading...**",
                        f"{rip_data['title']}.mp3",
                    )
                ),
            )

        thumb_image = [
            x
            for x in glob(os.path.join(TEMP_DOWNLOAD_DIRECTORY, str(s_time), "*"))
            if not x.endswith(".mp3")
        ][0]
        metadata = extractMetadata(createParser(f_name))
        duration = 0
        if metadata and metadata.has("duration"):
            duration = metadata.get("duration").seconds
        await v_url.client.send_file(
            v_url.chat_id,
            result,
            supports_streaming=True,
            attributes=[
                DocumentAttributeAudio(
                    duration=duration,
                    title=rip_data.get("title"),
                    performer=rip_data.get("uploader"),
                )
            ],
            thumb=thumb_image,
        )
        await v_url.delete()
    elif video:
        await v_url.edit(
            f"**Preparing to upload video:**\n`{rip_data.get('title')}`"
            f"\nby `{rip_data.get('uploader')}`"
        )
        f_path = glob(os.path.join(TEMP_DOWNLOAD_DIRECTORY, str(s_time), "*"))[0]
        # Noob way to convert from .mkv to .mp4
        if f_path.endswith(".mkv"):
            base = os.path.splitext(f_path)[0]
            os.rename(f_path, base + ".mp4")
            f_path = glob(os.path.join(TEMP_DOWNLOAD_DIRECTORY, str(s_time), "*"))[0]
        f_name = os.path.basename(f_path)
        with open(f_path, "rb") as f:
            result = await upload_file(
                client=v_url.client,
                file=f,
                name=f_name,
                progress_callback=lambda d, t: get_event_loop().create_task(  # type: ignore
                    progress(d, t, v_url, c_time, "**Uploading...**", f_name)
                ),
            )
        thumb_image = await get_video_thumb(f_path, "thumb.png")
        metadata = extractMetadata(createParser(f_path))
        duration = 0
        width = 0
        height = 0
        if metadata:
            if metadata.has("duration"):
                duration = metadata.get("duration").seconds
            if metadata.has("width"):
                width = metadata.get("width")
            if metadata.has("height"):
                height = metadata.get("height")
        await v_url.client.send_file(
            v_url.chat_id,
            result,
            thumb=thumb_image,
            attributes=[
                DocumentAttributeVideo(
                    duration=duration,
                    w=width,
                    h=height,
                    supports_streaming=True,
                )
            ],
            caption=f"[{rip_data.get('title')}]({url})",
        )
        os.remove(str(thumb_image))
        await v_url.delete()


def deEmojify(inputString):
    """Remove emojis and other non-safe characters from string"""
    return get_emoji_regexp().sub("", inputString)


CMD_HELP.update(
    {
        "img": ">`.img [count] <query> [or reply]`"
        "\nUsage: Does an image search on Google."
        "\nCan specify the number of results needed (default is 3).",
        "currency": ">`.currency <amount> <from> <to>`"
        "\nUsage: Converts various currencies for you.",
        "carbon": ">`.carbon <text> [or reply]`"
        "\nUsage: Beautify your code using carbon.now.sh\n"
        "Use .crblang <text> to set language for your code.",
        "google": ">`.google [count] <query> [or reply]`"
        "\nUsage: Does a search on Google."
        "\nCan specify the number of results needed (default is 3).",
        "wiki": ">`.wiki <query> [or reply]`" "\nUsage: Does a search on Wikipedia.",
        "ud": ">`.ud <query> [or reply]`" "\nUsage: Does a search on Urban Dictionary.",
        "tts": ">`.tts <text> [or reply]`"
        "\nUsage: Translates text to speech for the language which is set."
        "\nUse >`.lang tts <language code>` to set language for tts. (Default is English.)",
        "trt": ">`.trt <text> [or reply]`"
        "\nUsage: Translates text to the language which is set."
        "\nUse >`.lang trt <language code>` to set language for trt. (Default is English)",
        "yt": ">`.yt [count] <query> [or reply]`"
        "\nUsage: Does a YouTube search."
        "\nCan specify the number of results needed (default is 3).",
        "imdb": ">`.imdb <movie-name>`" "\nUsage: Shows movie info and other stuff.",
        "rip": ">`.ra <url>`"
        "\nUsage: Download videos from YouTube and convert to audio "
        "\n\n>`.rv <quality> <url>` (quality is optional)"
        "\nQuality: `144` `240` `360` `480` `720` `1080` `2160`"
        "\nUsage: Download videos from YouTube"
        "\n\n[Other supported sites](https://ytdl-org.github.io/youtube-dl/supportedsites.html)",
    }
)
