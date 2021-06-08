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
	"""
	def __init__(self, node_dict):
		self.simbad_id = node_dict["id"]
		self.form = node_dict["label"]
		self.description = node_dict["description"]
		self.label = node_dict["label"]
		self.skip = node_dict["status"]=="old"
		self.children = []
		self.parent = None
	
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
		parent, child = terms[d["parent"]], terms[d["child"]]
		parent.add_child(child)
	
	# only return root terms; everything else is in children
	return [t for t in terms.values() if t.parent is None]


def write_to(terms, dest_file, cur_level=1):
	"""produces our CSV output for a sequence of Term-s.
	"""
	for term in terms:
		sim_link = f"http://simbad.u-strasbg.fr/simbad/otypes#{term.simbad_id}"
		dest_file.write("{};{};{};{};{}\n".format(
			term.form, cur_level, term.label, term.description,
			f"skos:exactMatch({sim_link})"))
		write_to(term.children, dest_file, cur_level+1)


def main():
	forest = get_forest()
	with open("terms.csv", "w", encoding="utf-8") as f:
		write_to(forest, f)


if __name__=="__main__":
	main()
