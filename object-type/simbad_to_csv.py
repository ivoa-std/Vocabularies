#!/usr/bin/python3

"""
This script converts the SIMBAD-internal JSON vocabularies to our
standard CSV input; this loses some information relevant within SIMBAD,
so you can't go back from our input.

It's not clear just now (May 2021) whether SIMBAD will be the de-facto
maintainers of this vocabulary and hence whether this script will become
part of vocabulary operations.  Whoever touches this: Please update
this status statement.

Sorry for not documenting our input here; contact the SIMBAD staff if 
necessary.
"""

import json
import re
import sys
import urllib.parse as urlparse


class Term:
	"""a term in our vocabulary, constructed from simbad node dicts.

	What we keep here:

	* simbad_id: the short simbad form ("**")
	* form: the term identifier ("#whatever")
	* description
	* label: the human-readable one
	* skip: ignore this term in export
	* parent: None or a single other Term
	* children: sequence of Terms
	* uat_counterpart: UAT concept identifier as a string
	"""
	def __init__(self, node_dict):
		self.simbad_id = node_dict["id"]
		self.form = node_dict["label"]
		self.description = node_dict["description"]
		self.label = node_dict["label"]
		self.children = []
		self.parent = None
		self.uat_counterpart = None
	
	def add_child(self, term):
		if term.parent is not None:
			raise Exception(f"{term.form} already has a parent")
		term.parent = self
		self.children.append(term)


def get_forest():
	"""returns nodes/links from simbad as a forest of Term-s.
	"""
	with open("otype_nodes.json", "r", encoding="utf-8") as f:
		terms = dict((t.simbad_id, t) for t in (
			Term(d) for d in json.load(f)))

	with open("otype_links.json", "r", encoding="utf-8") as f:
		links = json.load(f)
	
	for d in links:
		try:
			parent, child = terms[d["parent"]], terms[d["child"]]
			parent.add_child(child)
		except KeyError:
			print(f"Bad link: {d['parent']} <- {d['child']}", file=sys.stderr)
	
	# only return root terms; everything else is in children
	return [t for t in terms.values() if t.parent is None], terms


def add_uat_links(terms):
	"""adds links to UAT equivalents to the terms in dicts.
	"""
	with open("uat-mapping.csv", encoding="utf-8") as f:
		for l in f:
			uat_concept, simbad_id = l.split("\t")[:2]
			if uat_concept.strip() in ['0', '']:
				continue

			# TODO: work out what to actually do with semicolons
			uat_concept = uat_concept.split(";")[0]

			simbad_id = re.sub("[{[](.*)[]}]", r"\1", simbad_id.strip()).strip()
			if simbad_id in terms:
				terms[simbad_id].uat_counterpart = (
					f"http://astrothesaurus.org/uat/{uat_concept}")
			else:
				print(f"No base for UAT mapping: {simbad_id}", file=sys.stderr)


def ivoafy_term_form(form):
	"""returns an experimental IVOA-ized term form, taking out, un-camel-casing,
	replacing odd characters, etc.
	"""
	# a few special cases
	form = {"HI": "h-i", "HII": "h-ii", "HII_G": "h-ii-g",
		"**": "multiple-star", "LINER": "liner", "QSO": "qso",
		"LMXB": "lmxb",	"HMXB": "hmxb", "ISM": "ism",
		"LPV*": "lpv-star", "LSB_G": "lsb-g", "MIR": "m-ir",
		"YSO": "yso", "AGB*": "agb-star", "AGN": "agn"}.get(form, form)
	# Three uppercase at the start: almost certainly a variable star class
	form = re.sub("^([A-Z][A-Z])([A-Z])", r"\1-\2", form)
	# Camel-case -> dashes
	form = re.sub("([a-z])([A-Z])", r"\1-\2", form).lower()
	# We can't have * in the label
	form = form.replace("*", "-star-")
	# Relations to words
	# Some special characters are well represented by dashes
	form = re.sub("[/_]", "-", form)
	# parens: dashify (they're always at the end of terms)
	form = re.sub(r"\(([^)]+)\)", r"-\1", form)
	return form.strip("-")
	

def write_to(terms, dest_file, cur_level=1):
	"""produces our CSV output for a sequence of Term-s.
	"""
	for term in terms:
		sim_link = "http://simbad.u-strasbg.fr/simbad/otypes#{}".format(
			urlparse.quote(term.simbad_id))

		relations = f"skos:exactMatch({sim_link})"
		if term.uat_counterpart:
			relations = f"{relations} skos:exactMatch({term.uat_counterpart})"

		dest_file.write("{};{};{};{};{}\n".format(
			ivoafy_term_form(term.form), cur_level, term.label, 
			term.description, relations))
		write_to(term.children, dest_file, cur_level+1)


def main():
	forest, terms = get_forest()
	add_uat_links(terms)
	with open("terms.csv", "w", encoding="utf-8") as f:
		write_to(forest, f)


if __name__=="__main__":
	main()
