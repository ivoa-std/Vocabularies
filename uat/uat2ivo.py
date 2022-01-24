#!/usr/bin/python3
"""
This script transforms the upstream UAT to an IVOA version.

The main challenge is to maintain a constant mapping from numeric
UAT concept identifiers to readable IVOA identifiers.  To maintain that,
we fetch the current mapping from the IVOA RDF repo.

What this outputs is a SKOS file for consumption by the IVOA ingestor.

Dependencies: python3, python3-requests, python3-unidecode.
"""

import re
import subprocess
import sys
import warnings
from xml.etree import ElementTree

import requests
import unidecode


# Upstream UAT RDF/XML
UAT_RDF_SOURCE = ("https://raw.githubusercontent.com"
    "/astrothesaurus/UAT/master/UAT.rdf")
# Downstream IVOA UAT; required here for existing maps
IVOA_RDF_SOURCE = "http://www.ivoa.net/rdf/uat"

# for debugging, override with local resources like:
# UAT_RDF_SOURCE = "http://localhost/UAT.rdf"
# IVOA_RDF_SOURCE = "http://localhost/rdf/uat"

UAT_TERM_PREFIX = "http://astrothesaurus.org/uat/"
IVO_TERM_PREFIX = "http://www.ivoa.net/rdf/uat#"


NS_MAPPING = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "ivoasem": "http://www.ivoa.net/rdf/ivoasem#",
}

for _prefix, _uri in NS_MAPPING.items():
    ElementTree.register_namespace(_prefix, _uri)
del _prefix, _uri


ABOUT_ATTR = ElementTree.QName(NS_MAPPING["rdf"], "about")
RESOURCE_ATTR = ElementTree.QName(NS_MAPPING["rdf"], "resource")
DESCRIPTION_TAG = ElementTree.QName(NS_MAPPING["skos"], "Concept")
IVOA_DEPRECATED_TAG = ElementTree.QName(NS_MAPPING["ivoasem"], "deprecated")
IVOA_USE_INSTEAD_TAG = ElementTree.QName(NS_MAPPING["ivoasem"], "useInstead")
SKOS_PREF_LABEL_TAG = ElementTree.QName(NS_MAPPING["skos"], "prefLabel")
XML_LANG_ATTR = ElementTree.QName(NS_MAPPING["xml"], "lang")


# There are extra triples for individual UAT concepts.  What is
# currently here as been taken from deprecations.txt.
# The keys are UAT identifiers, the values are dicts mapping properties
# to values; if these values start with http:, they count as resources,
# else they're considered string literals.
EXTRA_TRIPLES = {
"13": {
    SKOS_PREF_LABEL_TAG: "Accreting Binary Stars",
},
"132": {
    SKOS_PREF_LABEL_TAG: "Bailey type stars",
},
"143": {
    SKOS_PREF_LABEL_TAG: "Be type stars",
},
"146": {
    SKOS_PREF_LABEL_TAG: "Beryllium abundance",
},
"176": {
    SKOS_PREF_LABEL_TAG: "Boron abundance",
},
"275": {
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"comae",
    SKOS_PREF_LABEL_TAG: "Deprecated: Cometary atmospheres",
},
"279": {
    SKOS_PREF_LABEL_TAG: "Cometary studies",
},
"282": {
    SKOS_PREF_LABEL_TAG: "Compact binary components",
},
"284": {
    SKOS_PREF_LABEL_TAG: "Compact binary systems",
},
"298": {
    SKOS_PREF_LABEL_TAG: "Continuum radio emission",
},
"357": {
    SKOS_PREF_LABEL_TAG: "Darkrooms",
},
"392": {
    SKOS_PREF_LABEL_TAG: "Disk population",
},
"393": {
    SKOS_PREF_LABEL_TAG: "Disk stars",
},
"454": {
    SKOS_PREF_LABEL_TAG: "Elemental abundance",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"chemical-abundances",
},
"462": {
    SKOS_PREF_LABEL_TAG: "English mounts",
},
"471": {
    SKOS_PREF_LABEL_TAG: "Equinox correction",
},
"474": {
    SKOS_PREF_LABEL_TAG: "Eruptive binary stars",
},
"482": {
    SKOS_PREF_LABEL_TAG: "Exobiology",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"astrobiology",
},
"485": {
    SKOS_PREF_LABEL_TAG: "Exoplanet astrometry",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"astrometry",
},
"527": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Far Infrared Astronomy",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"far-infrared-astronomy"
},
"547": {
    SKOS_PREF_LABEL_TAG: "Fork mounts",
},
"554": {
    SKOS_PREF_LABEL_TAG: "Deprecated: FU Orionis Stars",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"fu-orionis-stars"
},
"579": {
    SKOS_PREF_LABEL_TAG: "Galaxy chemical composition",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"galaxy-abundances",
},
"587": {
    SKOS_PREF_LABEL_TAG: "Galaxy components",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"galaxy-structure",
},
"625": {
    SKOS_PREF_LABEL_TAG: "Galaxy voids",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"voids",
},
"636": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Gamma ray telescopes",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"gamma-ray-telescopes",
},
"649": {
    SKOS_PREF_LABEL_TAG: "German equatorial mounts",
},
"673": {
    SKOS_PREF_LABEL_TAG: "Gravitational microlensing [Exoplanets]",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"gravitational-microlensing",
},
"713": {
    SKOS_PREF_LABEL_TAG: "Helium abundance",
},
"720": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Henry Draper Catalogue",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"henry-draper-catalog",
},
"749": {
    SKOS_PREF_LABEL_TAG: "Horseshoe mounts",
},
"778": {
    SKOS_PREF_LABEL_TAG: "I galaxies",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"irregular-galaxies",
},
"781": {
    SKOS_PREF_LABEL_TAG: "Individual planetary nebulae",
},
"782": {
    SKOS_PREF_LABEL_TAG: "Individual quasars",
},
"815": {
    SKOS_PREF_LABEL_TAG: "Intergalactic voids",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"voids",
},
"817": {
    SKOS_PREF_LABEL_TAG: "Intermediate population stars",
},
"926": {
    SKOS_PREF_LABEL_TAG: "Lithium abundance",
},
"934": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Long period variable stars",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"long-period-variable-stars",
},
"945": {
    SKOS_PREF_LABEL_TAG: "Luminous blue variables",
},
"984": {
    SKOS_PREF_LABEL_TAG: "Solar M coronal region",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"solar-coronal-holes",
},
"1067": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Mira Variables",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"mira-variables"
},
"1103": {
    SKOS_PREF_LABEL_TAG: "Neutrino oscillation",
},
"1206": {
    SKOS_PREF_LABEL_TAG: "Penumbral filaments",
},
"1279": {
    SKOS_PREF_LABEL_TAG: "Polarimetry [Exoplanets]",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"polarimetry",
},
"1326": {
    SKOS_PREF_LABEL_TAG: "R Coronae Borealis stars",
},
"1333": {
    SKOS_PREF_LABEL_TAG: "Radial velocity methods [Exoplanets]",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"radial-velocity",
},
"1364": {
    SKOS_PREF_LABEL_TAG: "RC Aurigae stars",
},
"1411": {
    SKOS_PREF_LABEL_TAG: "RR Telescopii stars",
},
"1412": {
    SKOS_PREF_LABEL_TAG: "RRA stars",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"rrab-stars",
},
"1414": {
    SKOS_PREF_LABEL_TAG: "RRb stars",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"rrab-stars",
},
"1422": {
    SKOS_PREF_LABEL_TAG: "S Vulpeculae stars",
},
"1448": {
    SKOS_PREF_LABEL_TAG: "Seyfert's sextant",
},
"1480": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Solar composition",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"solar-composition",
},
"1505": {
    SKOS_PREF_LABEL_TAG: "Solar magnetism",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"solar-magnetic-fields",
},
"1520": {
    SKOS_PREF_LABEL_TAG: "Solar properties",
},
"1588": {
    SKOS_PREF_LABEL_TAG: "Stellar chemical composition",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"stellar-abundances",
},
"1591": {
    SKOS_PREF_LABEL_TAG: "Stellar composition",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"stellar-abundances",
},
"1598": {
    SKOS_PREF_LABEL_TAG: "Stellar elemental abundances",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"stellar-abundances",
},
"1665": {
    SKOS_PREF_LABEL_TAG: "Supernova evolution",
},
"1726": {
    SKOS_PREF_LABEL_TAG: "Two-spectrum binary stars",
},
"1798": {
    SKOS_PREF_LABEL_TAG: "White dwarf evolution",
},
"1802": {
    SKOS_PREF_LABEL_TAG: "Wilson-Bappu Effect",
},
"1831": {
    SKOS_PREF_LABEL_TAG: "Yoke mounts",
},
"2043": {
    SKOS_PREF_LABEL_TAG: "Stellar M coronal regions",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"stellar-coronal-holes",
},
"2071": {
    SKOS_PREF_LABEL_TAG: "Deprecated: Radiative Processes",
    IVOA_USE_INSTEAD_TAG: IVO_TERM_PREFIX+"radiative-processes"},
}


# set to True to ignore current IVOA mapping (in other words, never;
# that would quite certainly change quite a few terms on the IVOA
# side because previous mappings are forgotten).
BOOTSTRAP = False


def label_to_term(label:str):
    """returns an IVOA term for a label.

    "term" is the thing behind the hash.  It needs to consist of letters
    and a few other things exclusively.  We're replacing runs of one or
    more non-letters by a single dash.  For optics, we're also lowercasing
    the whole thing.

    ConceptMapping makes sure what's resulting is unique within the IVOA UAT.
    """
    return re.sub("[^a-z0-9]+", "-", 
        unidecode.unidecode(label).lower())


def iter_uat_concepts(tree:ElementTree.ElementTree, chatty:bool):
    """iterates over UAT skos:Concepts found in tree.

    If chatty is passed, various diagnostics may be generated.
    """
    for desc_node in tree.iter(DESCRIPTION_TAG):
        concept_uri = desc_node.get(ABOUT_ATTR)

        if not concept_uri.startswith(UAT_TERM_PREFIX):
            if chatty:
                raise Exception("Non-UAT concept {} encountered.".format(
                    concept_uri))
            continue

        yield desc_node


class ConceptMapping:
    """The mapping of concepts between UAT and IVOA.

    When instanciating this, it will go to the IVOA RDF repo to
    fill the mapping from what is already defined.
    """
    def __init__(self):
        self.uat_mapping = {}
        self.ivo_mapping = {}
        
        if not BOOTSTRAP:
            self._fill_from_ivoa()

    def __contains__(self, uat_uri: str):
        return uat_uri in self.uat_mapping

    def __getitem__(self, key:str):
        """returns an IVOA URI for an UAT URI.

        It will raise a KeyError for an unknown UAT URI.
        """
        return self.uat_mapping[key]

    def _fill_from_ivoa(self):
        """bootstraps the UAT <-> IOVA term mappings.
        """
        tree = ElementTree.parse(
            requests.get(IVOA_RDF_SOURCE, stream=True, 
                headers={"accept": "application/rdf+xml"}).raw)
        
        for concept in tree.iter(DESCRIPTION_TAG):
            em_el = concept.find("skos:exactMatch", NS_MAPPING)
            if em_el is None:
                warnings.warn("IVOA Concept without a UAT match: {}".format(
                    concept.get(ABOUT_ATTR)))
            else:
                self.add_pair(
                    em_el.get(RESOURCE_ATTR),
                    concept.get(ABOUT_ATTR))

    def add_pair(self, uat_uri:str, ivo_uri:str):
        """enters a mapping between uat_uri and ivo_uri to our mappings.

        It is an error if either of the URIs are already mapped in either
        direction.
        """
        if uat_uri in self.uat_mapping:
            raise Exception("Attempting to re-map UAT resource {}.\n"
                "  Existing relation: {}".format(
                    uat_uri, self.uat_mapping[uat_uri]))
        if ivo_uri in self.ivo_mapping:
            raise Exception("Attempting to re-map IVO resource {}.\n"
                "  Existing relation: {}".format(
                    ivo_uri, self.ivo_mapping[ivo_uri]))

        self.uat_mapping[uat_uri] = ivo_uri
        self.ivo_mapping[ivo_uri] = uat_uri

    def add_concept(self, desc_node:ElementTree.Element):
        """generates a new concept from a UAT-style rdf:Description element.

        It is an error to add a concept the URI of which already is in our
        mapping.
        """
        uat_uri = desc_node.attrib[ABOUT_ATTR]
        overrides = EXTRA_TRIPLES.get(uat_uri.split("/")[-1], {})

        label = desc_node.find("skos:prefLabel[@xml:lang='en']", NS_MAPPING)
        if SKOS_PREF_LABEL_TAG in overrides:
            label = overrides[SKOS_PREF_LABEL_TAG]

        if label is None:
            warnings.warn("Concept without prefLabel: {}".format(uat_uri))
            label = desc_node.find("rdfs:label[@xml:lang='en']", NS_MAPPING)

        if label is None:
            raise Exception("No preferred label on {}".format(uat_uri))

        if uat_uri not in self:
            ivo_uri = IVO_TERM_PREFIX+label_to_term(
                getattr(label, "text", label))
            if not BOOTSTRAP:
                print("New mapping: {} -> {}".format(uat_uri, ivo_uri))
            self.add_pair(uat_uri, ivo_uri)

    def update_from_etree(self, tree:ElementTree.ElementTree):
        """updates the mappings from an elementtree of the RDF-XML produced
        by the UAT.
        """
        for concept in iter_uat_concepts(tree, True):
            try:
                concept_uri = concept.get(ABOUT_ATTR)
                if concept_uri not in self:
                    self.add_concept(concept)
            except Exception:
                raise


def make_ivoa_input_skos(
        tree:ElementTree.ElementTree, 
        concept_mapping:ConceptMapping):
    """changes the tree in-place to have ivoa-style concepts and
    exactMatch declarations to the UAT concepts.
    """
    for concept in iter_uat_concepts(tree, False):
        uat_uri = concept.get(ABOUT_ATTR)
        ivo_uri = concept_mapping[uat_uri]
        concept.attrib[ABOUT_ATTR] = ivo_uri

        for new_rel, new_ob in EXTRA_TRIPLES.get(
                uat_uri.split("/")[-1], {}).items():
            if new_ob.startswith("http:"):
                ElementTree.SubElement(
                    concept,
                    new_rel,
                    attrib={RESOURCE_ATTR: new_ob})
            else:
                ElementTree.SubElement(
                    concept,
                    new_rel,
                    attrib={XML_LANG_ATTR: "en"}).text = new_ob

        # change UAT URIs of resources that our element references to 
        # the IVOA ones; leave everything we don't know how to map alone.
        for child in concept.findall("*"):
            related = child.get(RESOURCE_ATTR)
            if related in concept_mapping:
                child.attrib[RESOURCE_ATTR] = concept_mapping[related]

        # now we're done mapping, add a skos:exactMatch, as it won't
        # be touched any more
        ElementTree.SubElement(
            concept,
            ElementTree.QName(NS_MAPPING["skos"], "exactMatch"),
            attrib={RESOURCE_ATTR: uat_uri})

        # for owl:deprecated terms, add ivoasem_deprecated.
        deprecated = concept.find("owl:deprecated[.='true']", NS_MAPPING)
        if deprecated is not None:
            ElementTree.SubElement(
                concept,
                IVOA_DEPRECATED_TAG)
        
        # UAT upstram sometimes has multiple description elements.
        # They ought to fix that, but meanwhile we just merge them.
        defs = concept.findall("skos:definition", NS_MAPPING)
        if len(defs)>1:
            new_def = "\n\n".join(d.text for d in defs)
            for d in defs:
                concept.remove(d)
            def_el = ElementTree.SubElement(concept,
                ElementTree.QName(NS_MAPPING["skos"], "definition"))
            def_el.text = new_def


def main():
    concept_mapping = ConceptMapping()
    with open("/dev/null", "rb") as null:
        rapper = subprocess.Popen([
            "rapper", "-q", "-o", "rdfxml-abbrev", UAT_RDF_SOURCE],
            stdin=null, stdout=subprocess.PIPE, close_fds=True)
        tree = ElementTree.parse(rapper.stdout)
        if rapper.wait():
            raise Exception("Obtaining or filtering upstream UAT failed."
                " Giving up.")

    concept_mapping = ConceptMapping()
    concept_mapping.update_from_etree(tree)

    make_ivoa_input_skos(tree, concept_mapping)

    with open("uat.skos", "wb") as f:
        tree.write(f, encoding="utf-8")


if __name__=="__main__":
    main()

# vi:et:sta:sw=4
