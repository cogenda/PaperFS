My personal library of research papers.

As I migrate from MacOSX to Ubuntu, I'm no longer able to use Mekentosj's Papers to manage my collection of research papers.
After trying a few software, I decided to write my own library software.

I'm too lazy to write a good GUI, and I want to browse my library as a file system, so here is my attempt at it.

# License:
PaperFS is licensed under the GPLv3 license.

Bundled 3rd-party code:
 - fusepy (https://github.com/terencehonles/fusepy/), written by Giorgos Verigakis and Terence Honles.
 - The google-scholar parser is adapted from the code written by Christian Kreibich (http://www.icir.org/christian/scholar.html).

# Features:
 - Browse the library by title, authors, and tags
 - Search by creating a directory, and name it with your keyword
 - GUI for importing new papers from PDF files
 - Search and match bibliography records in Google Scholar
 - Import from the database of Mekentosj Papers

# Requirements:
Python dependencies:
 - python-u1db
 - pyqt4
 - python-popplerqt4
 - BeautifulSoup
 - pybtex

In addition, currently we read Chrome's cookie database from ~/.config/google-chrome/Default/Cookies. Supports for other browsers are yet to be added.

# Usage:
    cd /path/to/repo
    /path/to/src/importFromPDF.py
    /path/to/src/PaperFS.py mnt

# Design:

U1db is used as the data store, partly because of its promise of easy synchronization, although sync is not implemented yet.


