#!/usr/bin/env python

# * Use unidecode to make skos terms from labels (in uatbridge)

"""
A script to convert the CSV input format to various outputs.

Dependencies: python3, python3-rdflib, skosify (not packaged yet; see
https://pypi.org/project/skosify/)

See Appendix A of Vocabularies in the VO 2 for what this is and what
it's for.

This program is in the public domain.

In case of problems, please contact Markus Demleitner
<msdemlei@ari.uni-heidelberg.de>
"""

from configparser import ConfigParser
from xml.etree import ElementTree as etree

import contextlib
import csv
import itertools
import json
import os
import re
import subprocess
import textwrap
import shutil
import sys
import urllib.parse
import weakref

import rdflib

try:
    import skosify
    from rdflib.term import URIRef
except ImportError:
    sys.stderr.write("skosify and/or rdflib python modules missing;"
        " this will break as soon as SKOS vocabularies are processed.\n")


# Minimal required keys for a vocabulary construction
VOCABULARY_MANDATORY_KEYS = frozenset([
    "name", "timestamp", "title", "description", "authors"])

# this is defined in Vocabularies in the VO 2
KNOWN_PREDICATES = frozenset([
    "ivoasem:preliminary", "ivoasem:deprecated", "ivoasem:useInstead",
    "rdfs:subClassOf",
    "rdfs:subPropertyOf",
    "skos:broader", "skos:exactMatch",
    # well, this one isn't quite in VocInVO2 in late 2020.  Let's see.
    "skos:related",
    # ..and neither is this (which we need of facilities
    "skos:altLabel"])

# an RE our term URIs must match (we're not very diligent yet)
FULL_TERM_PATTERN = r"[\w\d#:/_.*%-]+"

# an RE our terms themselves must match
TERM_PATTERN = r"[\w\d_-]+"

IVOA_RDF_URI = "http://www.ivoa.net/rdf/"


HT_ACCESS_TEMPLATE = """# rewrite conditions for {name}
RewriteCond %{{HTTP_ACCEPT}} application/rdf\\+xml
RewriteRule ^{path}/?$ {path}/{timestamp}/{name}.rdf [R=303]

RewriteCond %{{HTTP_ACCEPT}} text/turtle
RewriteRule ^{path}/?$ {path}/{timestamp}/{name}.ttl [R=303]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json
RewriteRule ^{path}/?$ {path}/{timestamp}/{name}.json [R=303]

RewriteCond %{{HTTP_ACCEPT}} application/x-desise\\+json
RewriteRule ^{path}/?$ {path}/{timestamp}/{name}.desise [R=303]

RewriteRule ^{path}/?$ {path}/{timestamp}/{name}.html [R=303]
"""

NAMESPACES = {"dc": "http://purl.org/dc/terms/",
              "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
              "owl": "http://www.w3.org/2002/07/owl#",
              "xsd": "http://www.w3.org/2001/XMLSchema#",
              "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
              "foaf": "http://xmlns.com/foaf/0.1/",
              "ivoasem": "http://www.ivoa.net/rdf/ivoasem#",
              "skos": "http://www.w3.org/2004/02/skos/core#"}

TTL_HEADER_TEMPLATE = """@base {baseuri}.
@prefix : <#>.

""" + \
'\n'.join([f"@prefix {prefix}: <{namespace}> ."
           for prefix, namespace in NAMESPACES.items()]) + \
"""

<> a owl:Ontology;
    dc:created {timestamp};
    dc:creator {creators};
    dc:license {licenseuri};
    rdfs:label {title}@en;
    dc:title {title}@en;
    dc:description {description};
    ivoasem:vocflavour {flavour}.

dc:created a owl:AnnotationProperty.
dc:creator a owl:AnnotationProperty.
dc:title a owl:AnnotationProperty.
dc:description a owl:AnnotationProperty.

"""


JAVASCRIPT = """
"""

CSS_STYLE = """
html {
    font-family: sans;
}

h1 {
    margin-bottom: 3ex;
    border-bottom: 2pt solid #ccc;
}

tr {
    padding-top: 2pt;
    padding-bottom: 2pt;
    border-bottom: 1pt solid #ccc;
}

tr:target {
		border: 2pt solid yellow;
}

thead tr {
    border-top: 1pt solid black;
    border-bottom: 1pt solid black;
}

th {
    padding: 4pt;
}

.intro {
    max-width: 30em;
    margin-bottom: 5ex;
    margin-left: 2ex;
}

.outro {
    max-width: 30em;
    margin-top: 4ex;
}

table {
    border-collapse: collapse;
    border-bottom: 1pt solid black;
}

tr {
    padding: 5pt;
}

td {
    vertical-align: top;
    padding: 5pt;
}

th:nth-child(1),
td:nth-child(1) {
  background: #eef;
}

th:nth-child(3),
td:nth-child(3) {
  background: #eef;
}

th:nth-child(5),
td:nth-child(5) {
  background: #eef;
}


.draftwarning {
    border-left: 3pt solid red;
    padding-left: 6pt;
}

ul.compactlist {
    list-style-type: none;
    padding-left: 0pt;
    margin-block-start: 0pt;
    margin-block-end: 0pt;
}

ul.compactlist li {
    margin-bottom: 0.3ex;
}

label.popup {
	position: relative;
}

input.popup-control {
	display: none;
}

.popup-head {
	display: inline-block;
}

.popup-body {
	display: none;
}

.popup-control:checked ~ .popup-body {
	display: block;
	position: absolute;
	top: 0pt;
	left: 0pt;
	background: white;
	border: 1pt solid #555;
	z-index: 500;
	padding: 0.4rem 0.2rem;
	width: 20rem;
}

.proplabel {
  display: inline-block;
  position: relative;
	background: #442266;
	color: white;
	padding: 0.4rem 0.4rem;
	border-radius: 0.2em;
	white-space: nowrap;
	margin: 0.5rem 0.2rem;
}

#license {
    margin-top: 2rem;
    background-color: #ccc;
    padding: 0.5rem;
    font-size: 80%;
}

/* to a bit lighter with link underlines: we have a high link density
in our documents (and I don't care if this is a no-op on old browsers */
td a {
    text-decoration-color: transparent;
}

td a:hover {
    text-decoration-color: currentcolor;
    transition: all 0.2s ease-in;
}

"""


DEFAULT_LICENSE_HTML = """This vocabulary is made available under
<a href="">CC-0</a> by the <a
href="https://wiki.ivoa.net/twiki/bin/view/IVOA/IvoaSemantics">IVOA
Semantics Working Group</a>.  To learn how to improve and amend this
vocabulary, see <a href="http://ivoa.net/documents/Vocabularies/20200326/"
>Vocabularies in the VO 2</a>."""


class ReportableError(Exception):
    """is raised for expected and explainable error conditions.

    All other exceptions lead to tracbacks for further debugging.
    """


############ some utility functions

@contextlib.contextmanager
def work_dir(dir_name, clear_first=False):
    """a context manager for temporarily working in dir_name.

    dir_name, if non-existing, is created.  If clear_first=True is passed,
    the directory will be removed and re-created.
    """
    if clear_first and os.path.isdir(dir_name):
        shutil.rmtree(dir_name)

    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)
    owd = os.getcwd()
    os.chdir(dir_name)
    try:
        yield
    finally:
        os.chdir(owd)


def is_URI(s):
    """returns True if we believe s is a URI.

    This is a simple, RE-based heuristic.
    """
    return bool(re.match("[a-zA-Z]+://|#", s))


def append_with_sep(l, item, sep):
    """appends item to l, preceding it with sep if non-empty.

    This lets one emulate the ", ".join pattern for non-string lists.
    """
    if l:
        l.append(sep)
    l.append(item)


def pick_exactly_one(iter, errmsg, default=None):
    """returns the element in iter when there is only one.

    It raises an error with errmsg as an explanation otherwise.
    If default is non-None, it will be returned in case of an empty iter.
    """
    res = list(iter)
    if len(res)==0:
        if default is not None:
            return default
        raise ReportableError("Expected exactly one {} but got 0".format(
            errmsg))
    elif len(res)==1:
        return res[0]
    else:
        raise ReportableError("Expected exactly one {} but got {}".format(
            errmsg, len(res)))


def _expand_transitively(rn, cur_term, to_process):
    """helps close_transitively.

    See the explanation of the strategy there.
    """
    for narrower_term in rn.get(cur_term, []):
        if narrower_term in to_process:
            _expand_transitively(rn, narrower_term, to_process)
            to_process.remove(narrower_term)
        rn[cur_term].extend(rn.get(narrower_term, []))


def close_transitively(raw_narrower):
    """closes raw_narrower transitively.

    raw_narrower is a dict of lists; for every item i in a value list,
    that list is expanded by raw_narrower[i].

    This helps add_desise_narrowser in the case of non-SKOS vocabularies;
    it will not do anything sensible if d doesn't describe a tree.  In
    particular, it will not detect cycles and may go down in flames if
    there are any.
    """
    # our strategy: Pick a term to process and expand it and the subtree
    # below it post-order, removing anything visited from from our to-do list.
    # Repeat until we're done.
    to_process = set(raw_narrower)

    while to_process:
        _expand_transitively(raw_narrower, to_process.pop(), to_process)


def invert_wider(voc):
    """returns the inverse of the wider relationship on voc.

    This is either the simple inversion of wider in the SKOS
    case (where arbitrary graphs are possible and wider isn't transitive
    anyway) or its transitive closure (i.e., all terms reachable from t
    when following the branches).
    """
    inverted_wider = {}
    for t, term in voc.terms.items():
        for wider in term.get_objects_for(voc.wider_predicate):
            inverted_wider.setdefault(wider.lstrip("#"), []).append(t)

    if voc.flavour not in ["SKOS", "SKOS CSV"]:
        close_transitively(inverted_wider)

    return inverted_wider


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

                elif isinstance(child, etree.Element):
                        self.node.append(child)

                elif hasattr(child, "__iter__"):
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

        def dump(self, encoding="utf-8", dest_file=sys.stdout.buffer):
            etree.ElementTree(self.node).write(
                dest_file, encoding=encoding)


class _T(object):
        """a very simple templating engine.

        Essentially, you get HTML elements by saying T.elementname, and
        you'll get an _Element with that tag name.

        This is supposed to be instanciated to a singleton (here, T).
        """
        def __getattr__(self, key):
                return  _Element(key)

T = _T()


############ The term class and associated code

def make_ttl_literal(ob):
    """returns a turtle literal for an object.

    Really, at this point only strings and booleans are supported.
    However, if something looks like a URI (see is_URI), it's going to
    be treated as a URI; should we have an extra class for that?
    """
    if isinstance(ob, bool):
        return "true" if ob else "false"

    if not isinstance(ob, str):
        raise ValueError(f"Cannot make a literal from: {ob}")

    if is_URI(ob):
        return "<{}>".format(ob)

    elif re.match(r"\w+:\w+", ob):
        # TTL prefixed IRI, restricted to what we want to see.
        return ob

    else:
        if "\n" in ob:
            return '"""{}"""'.format(ob)
        else:
            return '"{}"'.format(ob.replace('"', '\\"'))


class Term(object):
    """A term in our vocabulary.

    Terms are constructed with the vocabulary the term is in
    and the items from the CSV as per Appendix A, except that
    parent terms are already resolved by the CSV parser.

    self.relations is a set of pairs of (predicate, object),
    where None in object is a blank node.
    """
    def __init__(self,
            vocabulary,
            term,
            label,
            description,
            parent=None,
            more_relations=None):

        if not re.match(TERM_PATTERN+"$", term):
            raise ReportableError("Term fragment {} does not match IVOA"
                " constraints.".format(term))

        self.relations = set([])
        self.vocabulary = weakref.proxy(vocabulary)
        self.term, self.label = term, label
        self.description = description
        if self.vocabulary.draft:
            self._add_relation("ivoasem:preliminary", None)
        if parent:
            self._set_parent_term(parent)
        if more_relations:
            try:
                self._parse_relations(more_relations)
            except Exception as msg:
                raise ReportableError("While parsing relations of"
                    f" {term}: {msg}")

        if not self.term:
            raise ValueError("Term with empty identifier")
        if not self.label.strip():
            raise ValueError(f"Term {self.term} has no label")

    def _add_relation(self, predicate, object):
        """adds a relation (self, predicate, object).

        This does some additional validation on what predicate is
        and thus should always be used in preference to directly
        appending to relations.
        """
        if not predicate in KNOWN_PREDICATES:
            raise ReportableError("Unknown predicate in ({}, {}, {})"
                .format(self.term, predicate, object))
        self.relations.add((predicate, object))

    def _set_parent_term(self, parent_term):
        """adds a triple declaring parent_term as "wider".

        The predicate here depends on the vocabulary flavour.

        There is a special case here for skos; there, parent_term
        can be a list, and a term can have multiple parents.
        """
        if (self.vocabulary.wider_predicate=="skos:broader"
                    and isinstance(parent_term, list)):
                for term in parent_term:
                    self._add_relation(
                        self.vocabulary.wider_predicate, term)

        else:
            self._add_relation(
                self.vocabulary.wider_predicate, parent_term)

    @staticmethod
    def _iter_relationship_literals(relations):
        """yields pairs of (predicate, object) for our relationship
        input format.

        That's a space-separated sequence of either predicate names or
        predicate-name(object-spec) specifications, where object-spec
        has balanced parentheses.

        The actual interpretation of object-spec happens in _parse_relations
        and by is_URI.  This should probably be improved to be less
        ad-hoc.

        And if our grammar gets any more complex, we should use a proper
        parser generator.
        """
        predicate, token_stack = None, None
        for mat in re.finditer(r"\(|\)|[^()\s]+", relations):
            token = mat.group(0).strip()

            if predicate is None:
                if not re.match(FULL_TERM_PATTERN+"$", token):
                    raise ValueError("Invalid predicate at {}: {}".format(
                            mat.start(), token))
                predicate = token

            else:
                # we have a predicate...
                if token_stack is None:
                    # ...and are not parsing an argument
                    if token=='(':
                        token_stack = []
                    elif token==')':
                        raise ValueError("Unexpected ) at {}".format(
                            mat.start()))
                    else:
                        # current predicate has no object
                        yield predicate, None

                        if not re.match(FULL_TERM_PATTERN+"$", token):
                            raise ValueError(
                                "Invalid predicate at {}: {}"
                                    .format(mat.start(), token))
                        predicate = token

                else:
                    # ...we are parsing argument
                    if token=='(':
                        token_stack.append(token)
                    elif token==')':
                        arg = token_stack.pop()+')'
                        if token_stack:
                            token_stack[-1] += arg
                        else:
                            # argument complete, reset parser
                            yield predicate, arg[:-1]
                            predicate, token_stack = None, None
                    else:
                        # don't discard whitespace here
                        token_stack.append(mat.group())

        if predicate:
            # yield a singleton if you don't have yet
            yield predicate, None

    def _parse_relations(self, relations):
        """adds relations passed in through the last column of our CSV.

        This parses {predicate[(object)]}.
        """
        for predicate, obj in self._iter_relationship_literals(relations):
            # a little hack: URI-fy plain objects by making them part of
            # the current vocabulary
            if obj and re.match(TERM_PATTERN+"$", obj):
                obj = "#"+obj

            self._add_relation(predicate, obj)

    def get_objects_for(self, predicate):
        """yields term names for which (predicate term) is in
        relationships.
        """
        for pred, term in self.relations:
            if pred==predicate:
                yield term

    def as_ttl(self):
        """returns a turtle representation of this term in a string.
        """
        fillers = {
            "term": self.term,
            "label": make_ttl_literal(self.label),
            "comment": make_ttl_literal(self.description or "N/D"),
            "term_type": self.vocabulary.term_class,
            "label_property": self.vocabulary.label_property,
            "description_property": self.vocabulary.description_property,
            }
        template = [
            "<#{term}> a {term_type}",
            "{label_property} {label}",
            "{description_property} {comment}"]

        for predicate, object in self.relations:
            if object is None:
                object = ":__"
            template.append("{} {}".format(
                predicate,
                make_ttl_literal(object)))

        return ";\n  ".join(template).format(**fillers)+"."

    def _format_term_as_html(self, term):
        """returns HTML for a term.

        This is going to be a link if the term exists in the parent
        vocabulary, or, for now, just the term.

        Passing in None (the blank node) is ok, too.  You'll get back None.
        """
        if term is None:
            return term
        if is_URI(term):
            return T.a(href=term)[term]

        if term[0]=='#':
            term = term[1:]

        if term in self.vocabulary.terms:
            return T.a(href="#"+term)["#"+term]
        else:
            return term

    def _format_more_relations(self):
        """yields HTML elements for the non-parent relationships
        this term has.

        We only select the relationships VocInVO2 talks about.
        """
        for prop, label in [
               ("ivoasem:useInstead", "Use Instead"),
               ("ivoasem:deprecated", "Deprecated Term"),
               ("skos:exactMatch", "Same As"),
               ("skos:related", "Related"),
               ("built-in:narrower", "Narrower")]:

            if prop=="built-in:narrower":
                objs = [self._format_term_as_html(t)
                    for t in sorted(self.vocabulary.inverted_wider.get(
                            self.term, []))]
            else:
                objs = [self._format_term_as_html(ob)
                    for ob in self.get_objects_for(prop)]

            if objs:
                # we have the property...
                non_nulls = [o for o in objs if o is not None]
                if non_nulls:
                    # ...and the property has non-blank objects
                    yield T.label(class_="popup")[
                        T.input(type="checkbox", class_="popup-control"),
                        T.span(class_="popup-head proplabel")[
                            label],
                        T.div(class_="popup-body")[
                            T.ul(class_="compactlist")[[
                                T.li[obj] for obj in objs]]]]

                else:
                    #... and the property only has blank nodes as objects
                    yield T.span(class_="proplabel")[label]

    def get_url(self):
        """returns this term's full RDF URI.
        """
        return self.vocabulary.baseuri+"#"+self.term

    def as_html(self):
        """returns elementtree for an HTML table line for this term.
        """
        preliminary = ("ivoasem:preliminary", None) in self.relations
        deprecated = ("ivoasem:deprecated", None) in self.relations

        formatted_relations = []
        for rel in self._format_more_relations():
            append_with_sep(formatted_relations, rel, T.br)

        if preliminary:
            row_class = "preliminary"
        elif deprecated:
            row_class = "deprecated"
        else:
            row_class = "term"

        parents = []
        for name in self.get_objects_for(self.vocabulary.wider_predicate):
            append_with_sep(parents, self._format_term_as_html(name), ", ")

        el =  T.tr(class_=row_class, id=self.term)[
            T.td(class_="term")[
                T.a(title="Copy the link URL for this term's RDF URI",
                    href=self.get_url(),
                    onclick=f"window.location.hash = '#{self.term}';"
                        " return false")[self.term],
                " (Preliminary)" if preliminary else "",
                " (Deprecated)" if deprecated else ""],
            T.td(class_="label")[self.label],
            T.td(class_="description")[self.description],
            T.td(class_="parent")[parents],
            T.td(class_="morerels")[formatted_relations],]

        return el


########### Vocabulary classes
# They do a bit much right now (parsing, managing, writing); we may
# want to refactor that and have vocabulary parsers and writers; but
# then the way this is built they aren't really independent, and so
# there's not much to be gained except smaller classes.

class Vocabulary(object):
    """The base class of Vocabularies.

    Vocabularies are constructed with the keys from vocabs.conf in a
    dictionary (which then show up in attributes).  See
    VOCABULARY_MANDATORY_KEYS for the minimal required keys.

    The attributes you can rely on here are:

    * baseuri: the vocabulary URI (the terms will be baseuri#term)
    * name: the vocabulary name; this must should consist of lowercase
      letters and underscores only.  Legacy vocabularies may use uppercase
      letters, too.
    * path: local path segments after rdf/.  This should only be given
      for legacy vocabularies and otherwise is just name.
    * filename: the name of the source file (should only be given if
      not <path>/terms.csv
    * timestamp, description, authors, title: as in vocabs.conf
    * draft: true if there's a key draft in vocabs.conf
    * terms: a dictionary of the terms as strings to the respective Term
      instances.
    * licenseuri: a license URI.  Only use for externally managed
      vocabularies; IVOA vocabularies are always CC-0.
    * hidden: if True, no META.INF is being written (meaning:
      the vocabulary will not show up in the repo).  Note at that right
      now hidden vocabularies will not install the right redirects into
      apache.  This should probably be fixed by making hidden-ness an
      explicit property in META.INF.
    * licensehtml: a human-readable license text that is reproduced
      verbatim in HTML.  Again, only use for externally managed vocabularies.
    * topconcepts: space-separated identifiers that are declared as SKOS
      top concepts.

    To derive a subclass, you need to define:

    * term_class -- the class of terms in this vocabulary
    * wider_predicate -- the predicate to link a term to its parent
    * label_property -- the predicate to assign a human-readable label
      to a term
    * description_property -- the predicate to assign a human-readable
      definition to a term
    * flavour -- a string that becomes the object to ivoasem:vocflavour
    """

    def __init__(self, meta):
        missing_keys = VOCABULARY_MANDATORY_KEYS-set(meta)
        if missing_keys:
            raise ReportableError("Vocabulary definition for {} incomplete:"
                " {} missing.".format(
                    meta.get("name", "<unnamed>"),
                    ", ".join(missing_keys)))

        self.draft = bool(meta.pop("draft", False))
        self.hidden = bool(meta.pop("hidden", False))

        path = meta.get("path", meta["name"])
        defaults = {
            "path": path,
            "baseuri": IVOA_RDF_URI+path,
            "filename": os.path.join(path, "terms.csv"),
            "licensehtml": DEFAULT_LICENSE_HTML,
            "licenseuri":
                "http://creativecommons.org/publicdomain/zero/1.0/",
            "topconcepts": "",
        }
        defaults.update(meta)
        meta = defaults

        for key, value in meta.items():
            setattr(self, key, value)

        self._load_terms()

        self.inverted_wider = invert_wider(self)

    def _read_terms_source(self):
        """must add a terms attribute self containing Term instances.

        This needs to be overridden in derived classes.
        """
        raise NotImplementedError("Base vocabularies cannot parse;"
            " use a derived class")

    def _load_terms(self):
        """arranges for the term attribute to be created.

        If you want to read something else than our custom CSV,
        override the _read_terms_source method, not this one; this
        method may do some additional validation useful for all
        classes of vocabularies.
        """
        try:
            # just see whether the file is readable.
            with open(self.filename, "rb") as f:
                _ = f.read(10)
        except IOError as ex:
            raise ReportableError(
                "Expected terms file {}.terms cannot be read: {}".format(
                    self.filename, ex))
        self._read_terms_source()

    def get_meta_dict(self):
        """returns the common meta items of this vocabulary as
        a str->str dictionary.
        """
        return {
            "baseuri": self.baseuri,
            "name": self.name,
            "path": self.path,
            "timestamp": self.timestamp,
            "description": self.description,
            "authors": self.authors,
            "title": self.title,
            "flavour": self.flavour,
            "licenseuri": self.licenseuri}

    def write_turtle(self):
        """writes a turtle representation of the vocabulary to
        the current directory as <name>.ttl.
        """
        with open(self.name+".ttl", "w", encoding="utf-8") as f:
            meta_items = dict((k, make_ttl_literal(v))
                for k, v in self.get_meta_dict().items())
            meta_items["creators"] = ",\n    ".join(
                    '[ foaf:name {} ]'.format(make_ttl_literal(n.strip()))
                for n in self.authors.split(";"))
            f.write(TTL_HEADER_TEMPLATE.format(**meta_items))

            for top_concept in self.topconcepts.split():
                f.write(f"<> skos:hasTopConcept <#{top_concept}>.\n")

            for _, term in sorted(self.terms.items()):
                f.write(term.as_ttl())
                f.write("\n\n")

    def write_jsonld(self):
        """writes a json-ld representation of the current vocabulary
        to current directory as <name>.

        rdflib's JSON-LD serializer does not support base URI.
        """
        triples = rdflib.Graph()
        with open(self.name+".ttl", "r", encoding="utf-8") as f:
            triples.parse(file=f, format="turtle")
        with open(self.name+".json", "wb") as f:
            triples.serialize(f, "json-ld",
                              context=NAMESPACES)

    def write_rdfx(self):
        """writes an RDF/X representation of the current vocabulary
        to current directory as <name>.rdf

        Since we never actually deal with proper RDF triples in here (so
        far), we create the RDF/X as an export of our turtle code.  Perhaps
        that's even for the better.
        """
        triples = rdflib.Graph()
        with open(self.name+".ttl", "r", encoding="utf-8") as f:
            triples.parse(file=f, format="turtle")
        with open(self.name+".rdf", "wb") as f:
            triples.serialize(f, "xml")

    def write_desise(self):
        """writes a dead simple semantics json into the current directory
        as <name>.desise.
        """
        with open(self.name+".desise", "w", encoding="utf-8") as f:
            json.dump(to_desise_dict(self), f, indent="  ")

    def get_html_body(self):
        """returns HTML DOM material for the terms in this vocabulary.
        """
        return T.table(class_="terms")[
        T.thead[
            T.tr[
                T.th(title="The formal name of the term as used in URIs"
                    )["Term"],
                T.th(title="Suggested label for the predicate"
                    " in human-facing UIs")["Label"],
                T.th(title="Human-readable description of the predicate"
                    )["Description"],
                T.th(title="If the predicate is in a wider-narrower relationship"
                    " to other predicates: The more general term.")["Parent"],
                T.th(title="Further properties of this term.")[
                    "More"],
            ],
        ],
        T.tbody[
            [t.as_html() for _, t in sorted(self.terms.items())]
        ]]

    def write_html(self):
        """writes an HTML representation of this vocabulary to the
        current directory as <name>.html.

        Override the get_html_body method to change this method's
        behaviour; what's in here is just the source format-independent
        material.
        """
        # licensehtml is an HTML literal; parse it first so the elements
        # don't get escaped
        license_element = etree.fromstring(
            '<p id="license">'+self.licensehtml+'</p>')
        doc = T.html(xmlns="http://www.w3.org/1999/xhtml")[
        T.head[
            T.title["IVOA Vocabulary: "+self.title],
            T.meta(http_equiv="content-type",
                content="text/html;charset=utf-8"),
            T.script(type="text/javascript") [JAVASCRIPT],
            T.style(type="text/css")[
                CSS_STYLE],],
        T.body[
            T.h1["IVOA Vocabulary: "+self.title],
            T.div(class_="intro")[
                T.p["This is the description of the vocabulary ",
                    T.code[self.baseuri],
                " as of {}.".format(self.timestamp)],
                T.p(class_="draftwarning")["This vocabulary is not"
                    " yet approved by the IVOA.  This means that"
                    " terms can still disappear without prior notice."]
                    if self.draft else "",
                T.p(class_="description")[self.description]],
                self.get_html_body(),
                T.p(class_="outro")["Alternate formats: ",
                    T.a(href=self.name+".rdf")["RDF/XML"],
                    ", ",
                    T.a(href=self.name+".ttl")["Turtle"],
                    ", ",
                    T.a(href=self.name+".json")["JSON-LD"],
                    ", ",
                    T.a(href=self.name+".desise")["desise"],
                    " (non-RDF json)."],
                license_element
       ]]

        with open(self.name+".html", "wb") as f:
            doc.dump(dest_file=f)

    def write_meta_inf(self):
        """writes a "short" META.INF for use by the vocabulary TOC generator
        at the IVOA web page to the current directory.
        """
        if self.hidden:
            return

        with open("META.INF", "w", encoding="utf-8") as f:
            f.write("Name: {}\n{}\n".format(
            self.title,
            textwrap.fill(
                self.description,
                initial_indent="Description: ",
                subsequent_indent="  ")))
            if self.draft:
                f.write("Status: Draft\n")

    def write_htaccess(self):
        """writes a fragment for the RDF .htaccess for content negotiation.

        This does not write a complete htaccess file; instead,
        make-rdf-index.py picks this up and combines it to the .htaccess in
        on directory up.

        This architecture is necessary because we want to rewrite
        vocabulary URIs before they get mangled by apache's DirectorySlash.
        """
        with open("htaccess-fragment.txt", "w", encoding="utf-8") as f:
            f.write(HT_ACCESS_TEMPLATE.format(
                timestamp=self.timestamp,
                path=self.path,
                name=self.name))

    def write_representation(self, fs_root):
        """builds the vocabulary's representation below fs_root.

        This puts ttl, html and rdf/x into <fs_root>/<name>/<timestamp>,
        and it arranges for a content-negotiating .htaccess file and
        a META.INF for the vocabulary index within <name>/.
        """
        with work_dir(
                os.path.join(
                    fs_root,
                    self.path,
                    self.timestamp),
                clear_first=True):
            self.write_turtle()
            self.write_html()
            self.write_jsonld()
            self.write_rdfx()
            self.write_desise()

        with work_dir(
                os.path.join(fs_root, self.path)):
            self.write_htaccess()
            self.write_meta_inf()


def comment_ignoring(f):
    """iterates over f, swallowing all empty or comment lines.

    (where a comment line starts with #).  This is to make
    the CSV reader ignore what people have used as comments in
    vocabulary sources.
    """
    for ln in f:
        if not ln.strip() or ln.startswith("#"):
            continue
        yield ln


class CSVBasedVocabulary(Vocabulary):
    """A vocabulary parsed from our custom CSV format.
    """
    def _read_terms_source(self):
        """creates Terms instances from our custom CSV format.
        """
        parent_stack = []
        last_term = None
        self.terms = {}
        with open(self.filename, "r", encoding="utf-8") as f:
            for index, rec in enumerate(csv.reader(
                    comment_ignoring(f), delimiter=";")):
                rec = [(s or None) for s in rec]

                try:
                    hierarchy_level = int(rec[1])
                    if hierarchy_level-1>len(parent_stack):
                        parent_stack.append(last_term)
                    while hierarchy_level-1<len(parent_stack):
                        parent_stack.pop()
                    last_term = rec[0]
                    if not is_URI(last_term):
                        last_term = "#"+last_term

                    if parent_stack:
                        parent = parent_stack[-1]
                    else:
                        parent = None

                    more_relations = None if len(rec)<5 else rec[4]

                    new_term = Term(
                        self,
                        rec[0],
                        rec[2],
                        rec[3],
                        parent,
                        more_relations)

                    self.terms[new_term.term] = new_term
                except IndexError:
                    sys.exit(
                        "{}, rec {}: Incomplete record {}.".format(
                            self.filename, index, rec))


class RDFSVocabulary(CSVBasedVocabulary):
    """A vocabulary based on RDFS properties.
    """
    label_property = "rdfs:label"
    description_property = "rdfs:comment"


class RDFPropertyVocabulary(RDFSVocabulary):
    """A vocabulary of rdf:Property instances.
    """
    term_class = "rdf:Property"
    wider_predicate = "rdfs:subPropertyOf"
    flavour = "RDF Property"


class RDFSClassVocabulary(RDFSVocabulary):
    """A vocabulary of rdfs:Class instances.
    """
    term_class = "rdfs:Class"
    wider_predicate = "rdfs:subClassOf"
    flavour = "RDF Class"


class SKOSMixin:
    """A mixin for the SKOS vocabulary classes.

    This gives the the basic classes and properties for SKOS.
    """
    term_class = "skos:Concept"
    wider_predicate = "skos:broader"
    label_property = "skos:prefLabel"
    description_property = "skos:definition"


class SKOSVocabulary(SKOSMixin, Vocabulary):
    """A SKOS vocabulary read from some sort of input SKOS via skosify.
    """
    flavour = "SKOS"

    def _normalise_uri(self, term):
        """returns a local term URI, which is the fragment if uri starts
        with the vocabulary URI, and the full term otherwise.
        """
        if "#" in term:
            voc_uri, local = term.split('#', 1)
            if voc_uri==self.baseuri:
                return local
            else:
                return term
        return term

    def _get_skos_objects_for(self, voc, rel, term):
        """returns (text) terms related to term in voc with the property rel.

        rel is a (text) URI of the property, term is a (text) URI.
        """
        for _, _, item in voc.triples((term, URIRef(rel), None)):
            yield self._normalise_uri(item)

    def _read_one_term(self, voc, term):
        label = pick_exactly_one(self._get_skos_objects_for(voc,
            "http://www.w3.org/2004/02/skos/core#prefLabel",
            term), "preferred label for {}".format(term))
        description = pick_exactly_one(self._get_skos_objects_for(voc,
            "http://www.w3.org/2004/02/skos/core#definition",
            term), "description for {}".format(term), "")
        parents = list("#"+t
            for t in self._get_skos_objects_for(
                voc,
                "http://www.w3.org/2004/02/skos/core#broader",
                term))

        more_relations = []

        # extra properties taking objects
        for prop_url, short_term in [
                ("http://www.w3.org/2004/02/skos/core#exactMatch",
                    "skos:exactMatch"),
                ("http://www.w3.org/2004/02/skos/core#related",
                    "skos:related"),
                ("http://www.ivoa.net/rdf/ivoasem#useInstead",
                    "ivoasem:useInstead")]:
            for match in self._get_skos_objects_for(
                    voc, prop_url, term):
                more_relations.append(
                    f"{short_term}({match})".format(match))

        # extra properties not taking objects
        for prop_url, short_term in [
                ("http://www.ivoa.net/rdf/ivoasem#deprecated",
                    "ivoasem:deprecated"),
                ("http://www.ivoa.net/rdf/ivoasem#preliminary",
                    "ivoasem:preliminary")]:
            for match in self._get_skos_objects_for(
                    voc, prop_url, term):
                more_relations.append(short_term)

        return Term(self,
            self._normalise_uri(term),
            label,
            description,
            parents,
            " ".join(more_relations))

    def _read_terms_source(self):
        """creates Terms instances from RDF/X SKOS.
        """
        self.terms = {}

        voc = skosify.skosify(self.filename)
        for term in voc.subjects():
            if not term.startswith(self.baseuri):
                # disregard all terms not belonging to us
                continue
            n = self._read_one_term(voc, term)
            self.terms[n.term] = n

        with open(self.filename, "r", encoding="utf-8") as f:
            self.original_rdfx = f.read()


class SKOSCSVVocabulary(SKOSMixin, CSVBasedVocabulary):
    """A SKOS vocabulary read from CSV.
    """
    flavour = "SKOS CSV"

    def get_meta_dict(self):
        # overridden because we want our products to say we are
        # SKOS and not SKOS CSV
        res = super().get_meta_dict()
        res["flavour"] = "SKOS"
        return res


############# dead simple semantics support

def to_desise_dict(voc):
    """returns a vocabulary as a dead simple semantics dictionary.
    """
    # take items from a vocabulary's meta dict rather than directly
    # from the class so we're always in sync with whatever the turtle
    # template gets.
    meta = voc.get_meta_dict()
    res = {}
    res["uri"] = meta["baseuri"]
    res["flavour"] = meta["flavour"]
    res["terms"] = {}

    for t in voc.terms.values():
        d = {
            "label": t.label,
            "description": t.description}

        for prop, obj in t.relations:
            if prop.startswith("ivoasem:"):
                d[prop[8:]] = (obj or "").lstrip("#")

        d["wider"] = []
        for w in t.get_objects_for(voc.wider_predicate):
            d["wider"].append(w.lstrip("#"))

        res["terms"][t.term] = d

    for t, props in res["terms"].items():
        props["narrower"] = voc.inverted_wider.get(t, [])

    return res


############# Top-level control

# a dictionary mapping vocabulary flavour to implementing class
VOCABULARY_CLASSES = dict((cls.flavour, cls)
    for cls in globals().values()
    if isinstance(cls, type)
        and issubclass(cls, Vocabulary)
        and getattr(cls, "flavour", None))


def get_vocabulary(config, vocab_name):
    """returns an a Vocabulary instance for vocab_name as described
    in the ConfigParser instance config.
    """
    meta = dict(config.items(vocab_name))
    if not "flavour" in meta:
        raise ReportableError("Vocabulary {} undefined in {}"
            " (or flavour declaration missing).".format(
                vocab_name, config_name))
    try:
        voc_flavour = meta.pop("flavour")
        cls = VOCABULARY_CLASSES[voc_flavour]
    except KeyError:
        raise ReportableError("Vocabulary {} has unknown flavour {}.".format(
            vocab_name, voc_flavour))

    meta["name"] = vocab_name
    return cls(meta)


def build_vocab_repr(config, vocab_name, dest_dir):
    """writes the representation of the vocabulary vocab_name (a section
    within config) as defined in the ConfigParser instance config.

    dest_dir is the root of the vocabularies repository (i.e., the
    generated hierarchy will be a child of it).
    """
    vocab = get_vocabulary(config, vocab_name)
    vocab.write_representation(dest_dir)


def parse_config(config_name):
    """parses the vocabulary configuration in config_name and returns
    a ConfigParser instance for it.
    """
    parser = ConfigParser()
    try:
        with open(config_name, "r", encoding="utf-8") as f:
            parser.read_file(f)
    except IOError:
        raise ReportableError(
            "Cannot open or read vocabulary configuration {}".format(
                input_name))

    return parser


########### User interface

def parse_command_line():
    import argparse
    parser = argparse.ArgumentParser(
        description='Creates RDF/X, HTML and turtle representations'
            ' for IVOA vocabularies.')
    parser.add_argument("vocab_name",
        help="Name (i.e., vocabs.conf section) of vocabulary to build."
        "  Use ALL to rebuild everything in the configuration file"
        " (e.g., after an update of the tooling).",
        type=str)
    parser.add_argument("--config",
        help="Name of the vocabulary config file.  This defaults"
        " to vocabs.conf in the current directory.",
        type=str,
        dest="config_name",
        default="vocabs.conf")
    parser.add_argument("--root-uri",
        help="Use URI as the common root of the vocabularies instead of"
        " the official IVOA location as the root of the vocabulary"
        " hierarchy.  This is for test installations at this point.",
        action="store",
        dest="root_uri",
        default="http://www.ivoa.net/rdf/",
        metavar="URI")
    parser.add_argument("--dest-dir",
        help="Create output hierarchy below PATH.",
        action="store",
        dest="dest_dir",
        default="build",
        metavar="PATH")
    args = parser.parse_args()

    if not args.root_uri.endswith("/"):
        args.root_uri = args.root_uri+"/"

    return args


def main():
    args = parse_command_line()
    config = parse_config(args.config_name)

    if args.vocab_name=="ALL":
        to_build = config.sections()
    else:
        to_build = [args.vocab_name]

    for vocab_name in to_build:
        try:
            build_vocab_repr(config, vocab_name, args.dest_dir)
        except Exception:
            sys.stderr.write("While building {}:\n".format(vocab_name))
            raise


if __name__=="__main__":
    try:
        main()
    except ReportableError as msg:
        import traceback;traceback.print_exc()
        sys.stderr.write("*** Fatal: {}\n".format(msg))
        sys.exit(1)

# vi:sw=4:et:sta
