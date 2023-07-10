"""
This script creates an index.html for the www.ivoa.net/rdf.

It does this by recursively looking for META.INF files below the directory
passed in its argument.  From these, it extracts vocabulary metadata, which
it in turn uses to generate the index.html in that directory from the
index.template file there.

META.INF files are simple key-value files with the following keys:

* Name -- the vocabulary name (very short phrase)
* Description -- a longer explanation what the vocabulary is intended for
* Status -- optional.  If its value is "Draft", the vocabulary
  will be marked as not stable yet.

Date last changed and the vocabulary URL is inferred from the standard
(W3C best practice) directory structure.

For external or irregular vocabularies, there are two additional keys:

* Last Change -- date of last change to the vocabulary; use ISO format
  YYYY-MM-DD
* URI -- the vocabulary URI.

META.INF files have one key-value pair per line; indented lines are
continuation lines.

Here's an example:

------------8<------------
Name: Content levels for VO resources
Description: This vocabulary enumerates the intended audiences for
  resources in the Virtual Observatory.  It is designed to enable
  discovery queries like "only research-level data" or "resources
  usable in school settings".
------------8<------------

index.template is just treated as a text file, and we will replace the
string VOCAB_LIST_HERE with rendered HTML.

Written by Markus Demleitner <msdemlei@ari.uni-heidelberg.de>, August 2018
"""

import glob
import io
import re
import os
import sys

from xml.etree import ElementTree as etree

# this is the URI that should complete a local relative path to
# a resolvable URI
IVOA_RDF_BASE = "http://www.ivoa.net/rdf"


class ReportableError(Exception):
    pass


def die(msg):
    sys.stderr.write(msg)
    sys.exit(1)


############ tiny DOM start (snarfed and simplified from DaCHS stanxml)
# (used to write HTML)

class _Element(object):
    """An element within a DOM.

    Essentially, this is a simple way to build elementtrees.  You can
    reach the embedded elementtree Element as node.

    Add elements, sequences, etc, using indexation, attributes using function
    calls; names with dashes are written with underscores, python
    reserved words have a trailing underscore.
    """
    _generator_t = type((x for x in ()))

    def __init__(self, name):
        self.node = etree.Element(name)

    def add_text(self, tx):
        """appends tx either the end of the current content.
        """
        if len(self.node):
            self.node[-1].tail = (self.node[-1].tail or "")+tx
        else:
            self.node.text = (self.node.text or "")+tx

    def __getitem__(self, child):
        if child is None:
            return

        elif isinstance(child, str):
            self.add_text(child)

        elif isinstance(child, (int, float)):
            self.add_text(str(child))

        elif isinstance(child, _Element):
            self.node.append(child.node)

        elif isinstance(child, (list, tuple, self._generator_t)):
            for c in child:
                self[c]
        else:
            raise Exception("%s element %s cannot be added to %s node"%(
                type(child), repr(child), self.node.tag))
        return self

    def __call__(self, **kwargs):
        for k, v in kwargs.items():
            if k.endswith("_"):
                k = k[:-1]
            k = k.replace("_", "-")
            self.node.attrib[k] = v
        return self

    def dump(self, encoding="utf-8", dest_file=sys.stdout):
      etree.ElementTree(self.node).write(dest_file)


class _T(object):
    """a very simple templating engine.

    Essentially, you get HTML elements by saying T.elementname, and
    you'll get an _Element with that tag name.

    This is supposed to be instanciated to a singleton (here, T).
    """
    def __getattr__(self, key):
        return  _Element(key)

T = _T()
############ tiny DOM end


def find_meta_infs(src_dir):
    """iterates over path names leading to META.INF files below the src_dir.
    """
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for name in filenames:
            if name=="META.INF":
                yield os.path.join(dirpath, name)


def parse_meta(f):
    """returns a dictionary from the key-value pairs in f.

    See module docstring for the syntax rules.
    """
    cur_key, res = None,{}

    for ln_no, ln in enumerate(f):
        if not ln.strip():
            continue

        mat = re.match(r"([\w ]+):(.*)", ln)
        if mat:
            cur_key = mat.group(1).strip().lower()
            res[cur_key] = mat.group(2).strip()
            continue

        mat = re.match(r"\s+(.*)", ln)
        if mat:
            if not cur_key:
                raise ReportableError(
                    "Syntax error in {}, {}: continuation line"
                    " not allowed here".format(f.name, ln_no))
            res[cur_key] += " "+mat.group(1).strip()
            continue

        raise ReportableError("Syntax error in {}, {}: neither key-value"
            " pair nor continuation line".format(f.name, ln_no))

    return res


def iter_voc_descriptors():
    """iterates over dictionaries describing the vocabularies below the
    current directory.

    Each dictionary has the keys name, description, last change, and uri.
    """
    for path in find_meta_infs("."):
        with open(path, "r", encoding="utf-8") as f:
            meta = parse_meta(f)

        # fill out defaults for local vocabularies; the date last changed
        # is the newest (lexically largest) subdirectory as per W3C
        # best practice
        if "last change" not in meta:
            versions = sorted(glob.glob(
                os.path.join(
                    os.path.dirname(path), "2*")))
            if versions:
                meta["last change"] = versions[-1].split("/")[-1]
            else:
                raise ReportableError("{} does not define a last changed"
                    " date and no local vocab versions are found.".format(
                    path))

        # the uri is inferred through the path
        if "uri" not in meta:
            meta["uri"] = IVOA_RDF_BASE+(
                os.path.dirname(path).lstrip("."))

        yield meta


def get_vocab_table(vocabs):
    """returns an HTML table for vocabs in a native string.
    """
    dom = T.div[
    T.style(type="text/css")["""
table.vocab {
  border-spacing: 3pt;
  border-collapse: collapse;
  margin-top: 3ex;
  margin-top: 2ex;
  border-top: 2pt solid grey;
  border-bottom: 2pt solid grey;
}

table.vocab thead tr th {
  border-top: 1pt solid grey;
  font-weight: bold;
  padding: 3pt;
}

table.vocab tbody tr td {
  border-top: 1pt solid grey;
  border-bottom: 1pt solid grey;
  padding: 3pt;
}

table.vocab tbody tr td:nth-child(odd) {
  background-color: #EEE;
}
table.vocab thead tr th:nth-child(odd) {
  background-color: #EEE;
}

td.date-cell {
  white-space: nowrap;
}

span.status {
  color: #E44;
  font-weight: bold;
}

.status-draft {
  color: #666;
}
        """],
    T.table(class_="vocab")[
        T.thead[
            T.tr[
                T.th(title="The informal vocabulary name")["Name"],
                T.th(title="The date this vocabulary was last changed"
                    " (the version indicator)")["Last Change"],
                T.th(title="The vocabulary URI as used in RDF")["URI"],
                T.th(title="Use and function of this vocabulary")[
                    "Description"]],
            T.tbody[[
                T.tr(class_="status-"+voc.get("status", "stable"))[
                    T.td[voc["name"],
                        [T.br, T.span(class_="status")["DRAFT"]]
                            if voc.get("status")=="Draft" else ""],
                    T.td(class_="date-cell")[voc["last change"]],
                    T.td(class_="url-cell")[
                        T.a(href=voc["uri"])[voc["uri"]]],
                    T.td[voc["description"]]]
                for voc in vocabs]]]]]

    f = io.BytesIO()
    dom.dump(dest_file=f)
    return f.getvalue().decode("utf-8")


def fill_template(template, vocabs):
    """returns a (native) string with our HTML template filled out with
    the stuff in vocabulary.

    vocabs is a sequence of vocabulary descriptors as returned by
    iter_voc_descriptors.
    """
    return template.replace("VOCAB_LIST_HERE",
        get_vocab_table(vocabs))


def get_voc_sort_key(voc):
    """returns a sort key for a vocabulary.

    Accepted vocabularies are always sorted in front of draft ones.
    In each class, order is by name.
    """
    return (voc.get("status")=="Draft", voc["name"])


def main():
    if len(sys.argv)!=2:
        die("Usage: {} <rdf-directory>\n".format(sys.argv[0]))

    try:
        with open("index.template", "r", encoding="utf-8") as f:
            template = f.read()
    except IOError:
        die("Cannot read HTML index.template")

    try:
        os.chdir(sys.argv[1])
        vocabs = list(iter_voc_descriptors())
        vocabs.sort(key=get_voc_sort_key)
        rendered = fill_template(template, vocabs)

        # don't inline fill_template below lest incomplete results be
        # written
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(rendered)
    except ReportableError as msg:
        die(str(msg))


if __name__=="__main__":
    main()


# vi:sw=4:et:sta
