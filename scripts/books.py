import datetime as dt
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlretrieve

import frontmatter
import hyperlink
import inquirer

from . import goodreads, utils


@utils.book_data
def get_book_from_input():
    questions = [
        inquirer.Text("title", message="What’s the title of the book?"),
        inquirer.Text("author", message="Who’s the author?"),
        inquirer.Text("publication_year", message="When was it published?"),
        inquirer.Text("cover_image_url", message="What’s the cover URL?"),
        inquirer.Text("cover_desc", message="What’s the cover?"),
        inquirer.Text("isbn10", message="Do you know the ISBN-10?"),
        inquirer.Text("isbn13", message="Do you know the ISBN-13?"),
        inquirer.List(
            "series",
            message="Is this book part of a series?",
            choices=[("Yes", True), ("No", False)],
            default=False,
        ),
    ]

    answers = inquirer.prompt(questions)

    if answers["series"]:
        series_questions = [
            inquirer.Text("series", message="Which series does this book belong to?"),
            inquirer.Text(
                "series_position",
                message="Which position does the book have in its series?",
            ),
        ]
        answers = {**answers, **inquirer.prompt(series_questions)}
    return answers


def get_date(prompt):
    date_read = inquirer.list_input(
        message=prompt, choices=["today", "yesterday", "another day"],
    )
    today = dt.datetime.now()

    if date_read == "today":
        return today.date()
    if date_read == "yesterday":
        yesterday = today - dt.timedelta(days=1)
        return yesterday.date()
    date_read = None
    while True:
        date_read = inquirer.text(message="When did you finish reading it?")

        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_read.strip()):
            return dt.datetime.strptime(date_read, "%Y-%m-%d").date()
        elif re.match(r"^\d{1,2} [A-Z][a-z]+ \d{4}$", date_read.strip()):
            return dt.datetime.strptime(date_read, "%d %B %Y").date()
        else:
            print(f"Unrecognised date: {date_read}")


def get_review_info(date_started=None):
    if not date_started:
        date_started = get_date("When did you start reading this book?")
    date_read = get_date("When did you finish reading it?")
    rating = inquirer.list_input(
        message="What’s your rating?",
        choices=[("⭐⭐⭐⭐⭐", 5), ("⭐⭐⭐⭐", 4), ("⭐⭐⭐", 3), ("⭐⭐", 2), ("⭐", 1)],
    )
    if rating > 3:
        did_not_finish = False
    else:
        did_not_finish = not inquirer.list_input(
            message="Did you finish the book?", choices=[("yes", True), ("no", False)],
        )

    return {
        "date_read": date_read,
        "rating": rating,
        "did_not_finish": did_not_finish,
    }


def save_cover(slug, cover_image_url):
    filename, headers = urlretrieve(cover_image_url)

    if headers["Content-Type"] == "image/jpeg":
        extension = ".jpg"
    elif headers["Content-Type"] == "image/png":
        extension = ".png"
    elif headers["Content-Type"] == "image/gif":
        extension = ".gif"
    else:
        raise Exception(f"Unknown cover format: {headers}")

    url_path = hyperlink.URL.from_text(cover_image_url).path
    extension = os.path.splitext(url_path[-1])[-1]

    cover_name = f"{slug}{extension}"
    destination = Path("src") / "covers" / cover_name

    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(filename, destination)

    return cover_name


def get_out_path(entry, entry_type):
    if entry_type == "review":
        year = entry["review"]["date_read"].year
        out_dir = f"reviews/{year}"
    elif entry_type == "to_read":
        entry["plan"] = {
            "date_added": dt.datetime.now().date(),
        }
        out_dir = "to-read"
    else:
        out_dir = "currently-reading"
    out_path = Path("src") / out_dir / f"{entry['book']['slug']}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


def add_book(auth):
    choice = inquirer.list_input(
        "Do you want to get the book data from Goodreads, or input it manually?",
        choices=["goodreads", "manually"],
        default="goodreads",
    )
    entry_type = inquirer.list_input(
        message="What type of book is this?",
        choices=[
            ("One I’ve read", "review"),
            ("One I’m currently reading", "currently_reading"),
            ("One I want to read", "to_read"),
        ],
    )

    new_entry = (
        get_book_from_input()
        if choice == "manually"
        else goodreads.get_book_from_goodreads(auth=auth)
    )
    if entry_type == "review":
        review_info = get_review_info()
        new_entry["review"] = {key: review_info[key] for key in ("date_read", "rating")}
        if review_info["did_not_finish"]:
            new_entry["review"]["did_not_finish"] = True

    new_entry["book"]["cover_image"] = save_cover(
        slug=new_entry["book"]["slug"],
        cover_image_url=new_entry["book"]["cover_image_url"],
    )

    out_path = get_out_path(new_entry, entry_type)

    with open(out_path, "wb") as out_file:
        frontmatter.dump(frontmatter.Post(content="", **new_entry), out_file)
        out_file.write(b"\n")

    subprocess.check_call([os.environ.get("EDITOR", "vim"), out_path])

    if new_entry["book"].get("goodreads"):
        if inquirer.list_input(
            message="Do you want to push these changes to Goodreads?",
            choices=[("yes", True), ("no", False)],
        ):
            goodreads.push_to_goodreads(
                data=new_entry, path=out_path, auth=auth, entry_type=entry_type
            )


def change_book(auth):
    # TODO: load all books
    # TODO: search / suggest
    # TODO: change state or open editor
    # TODO update on goodreads, if wanted
    pass