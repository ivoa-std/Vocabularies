"""
This script transforms the upstream UAT to an IVOA version.

The main challenge is to maintain a constant mapping from numeric
UAT concept identifiers to readable IVOA identifiers.  To maintain that,
we fetch the current mapping from the IVOA RDF repo.

What this outputs is a SKOS file for consumption by the IVOA ingestor.
"""

import re
import warnings
#warnings.filterwarnings("ignore", message="Non-Concept:")

from xml.etree import ElementTree
import requests


UAT_RDF_SOURCE = "https://raw.githubusercontent.com/astrothesaurus/UAT/master/UAT.rdf"
# for now, convert what's coming from there with
# rapper -o rdfxml-abbrev input-from-github.rdf > input.rdf
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


# set to True to ignore current IVOA mapping (in other words, never;
# that would quite certainly change quite a few terms on the IVOA
# side because previous mappings are forgotten).
BOOTSTRAP = True


def label_to_term(label:str):
	"""returns an IVOA term for a label.

	"term" is the thing behind the hash.  It needs to consist of letters
	and a few other things exclusively.  We're replacing runs of one or
	more non-letters by a single dash.  For optics, we're also lowercasing
	the whole thing.

	ConceptMapping makes sure what's resulting is unique within the IVOA UAT.
	"""
	return re.sub("[^A-Za-z0-9]+", "-", label).lower()


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
		if BOOTSTRAP:
			self.uat_mapping = {}
			self.ivo_mapping = {}
		else:
			raise NotImplementedError("Can't read from IVOA yet")

	def __contains__(self, uat_uri: str):
		return uat_uri in self.uat_mapping

	def __getitem__(self, key:str):
		"""returns an IVOA URI for an UAT URI.

		It will raise a KeyError for an unknown UAT URI.
		"""
		return self.uat_mapping[key]

	def add_pair(self, uat_uri:str, ivo_uri:str):
		"""enters a mapping between uat_uri and ivo_uri to our mappings.

		It is an error if either of the URIs are already mapped in either
		direction.
		"""
		if uat_uri in self.uat_mapping:
			raise Exception("Attempting to re-map {}".format(uat_uri))
		if ivo_uri in self.ivo_mapping:
			raise Exception("Attempting to re-map {}".format(ivo_uri))

		self.uat_mapping[uat_uri] = ivo_uri
		self.ivo_mapping[ivo_uri] = uat_uri

	def add_concept(self, desc_node:ElementTree.Element):
		"""generates a new concept from a UAT-style rdf:Description element.

		It is an error to add a concept the URI of which already is in our
		mapping.
		"""
		uat_uri = desc_node.attrib[ABOUT_ATTR]
		label = desc_node.find("skos:prefLabel[@xml:lang='en']", NS_MAPPING)

		if label is None:
			warnings.warn("Concept without prefLabel: {}".format(uat_uri))
			label = desc_node.find("rdfs:label[@xml:lang='en']", NS_MAPPING)

		if label is None:
			raise Exception("No preferred label on {}".format(uat_uri))

		self.add_pair(
			desc_node.attrib[ABOUT_ATTR],
			IVO_TERM_PREFIX+label_to_term(label.text))

	def update_from_etree(self, tree:ElementTree.ElementTree):
		"""updates the mappings from an elementtree of the RDF-XML produced
		by the UAT.
		"""
		for concept in iter_uat_concepts(tree, True):
			concept_uri = concept.get(ABOUT_ATTR)
			if concept_uri not in self:
				self.add_concept(concept)


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

		# change UAT URIs of resources referred to to IVOA ones; leave everything 
		# we don't know how to map alone.
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

		# finally, do extra housekeeping
		deprecated = concept.find("owl:deprecated[.='true']", NS_MAPPING)
		if deprecated is not None:
			ElementTree.SubElement(
				concept,
				IVOA_DEPRECATED_TAG,
				attrib={RESOURCE_ATTRIB: "do_not_care"})


def main():
	f = open("input.rdf", "rb")
	tree = ElementTree.parse(f)
	f.close()

	concept_mapping = ConceptMapping()
	concept_mapping.update_from_etree(tree)

	make_ivoa_input_skos(tree, concept_mapping)

	with open("output.skos", "wb") as f:
		tree.write(f, encoding="utf-8")


if __name__=="__main__":
	main()
