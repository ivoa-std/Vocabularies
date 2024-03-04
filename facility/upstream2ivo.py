"""
Translate the upstream JSON-encoded facilities list to our CSV input.
"""

import csv
import json
import os
import re
import urllib.request as urlrequest


SRC_URI = ("https://raw.githubusercontent.com/epn-vespa/FacilityList"
	"/master/data/obs-facilities_vocabulary/obs-facilities_vocabulary.json")


def read_source():
	"""returns a string containing the upstream json.

	To simplify development, a local file temp-devel-cache.json will
	be read instead of the remote resource if present.
	"""
	if os.path.exists("temp-devel-cache.json"):
		with open("temp-devel-cache.json", encoding="utf-8") as f:
			return f.read()
	
	f = urlrequest.urlopen(SRC_URI)
	try:
		return f.read()
	finally:
		f.close()


def iter_recs():
	"""yields term, level, label, description, more_relation tuples
	from the upstream JSON.

	That's the tuples we have in VocInVO2 CSVs.
	"""
	upstream_concepts = json.loads(read_source())

	for concept in upstream_concepts:
		term = re.sub("[^a-z0-9-]", "-", concept["@id"])
		level = 1
		label = concept["rdfs:label"]
		description = concept["rdfs:comment"]

		more_relations = []
		for alt_label in set(concept["skos:sameAs"]):
			if not alt_label.strip():
				continue
			if ")" in alt_label:
				continue
				raise ValueError(f"No parentheses allowed in labels: {alt_label}")
			more_relations.append(f"skos:altLabel({alt_label})")
		
		yield term, level, label, description, " ".join(more_relations)


def main():
	with open("terms.csv", "w", encoding="utf-8") as f:
		csv.writer(f, delimiter=";").writerows(iter_recs())


if __name__=="__main__":
	main()
