These are the sources for the IVOA vocabularies as specified in
`Vocabularies in the VO 2`_.  This repository is maintained by the
chairs of the Semantics Working Group; other persons usually have no
reason to interact with it.

.. _Vocabularies in the VO 2: https://ivoa.net/documents/Vocabularies/

Vocabulary users would use the built vocabularies from
http://www.ivoa.net/rdf.  To propose changes, please follow the `VEP
process`_.

.. _VEP process: https://ivoa.net/documents/Vocabularies/20210525/REC-Vocabularies-2.0.html#tth_sEc5.2.1

The rest of the README essentially is a crib sheet for the maintainers,
and it is to be read together with Appendix A of the Vocabularies
recommendation.


Repository Organisation
=======================

In this repository, each vocabulary is in a subdirectory of its own; the
directory structure copies what is eventually on ivoa.net; vocabulary
names with several segments ("datalink/core", "voresource/relationship")
are supported but discouraged.

In each subdirectory, a file terms.csv contains the actual terms (there
are exceptions, in particular for SKOS input).

Per-vocabulary metadata is given in a single file in the root of the
repository called ``vocabs.conf``.  This, in particular, controls the
versioning of the vocabularies.  See below for a discussion of its
format.


Operation
=========

To build a single vocabulary, run::

  python3 convert.py <vocabulary name>

where ``<vocabulary name>`` is one of the keys in ``vocabs.conf``.

This will leave a deployable hierarchy for the vocabulary in the
``build`` subdirectory.  For instance, after calling::

  python3 convert.py refposition

there will be a subdirectory ``build/refposition`` containing the
vocabulary artefacts in a child named for the vocabulary version.  In
order to make a web server work with this, you also need to update the
.htaccess in the build directory.  This happens by calling::

  python3 make-rdf-index.py build

See below for actual deployment.


Defining Vocabularies
=====================

By default, our vocabularies are kept in CSV files.  The CSV separator
is ";".  Since our descriptions will have lots of commas in them, this
helps to keep the necessity for quoting low.

The columns or the CSVs are:

subject; level; label; description; more_relations

The fields mean:

:term:
  This is the actual, machine-readable vocabulary term.  Please only use
  letters, digits, underscores, and dashes here.  It is *not* intended
  for human consumption as such, although in the VO we prefer terms that
  make sense in English.
:level:
  This is used for simple input of wider/narrower relationships.
  It must be 1 for “root” terms.  Terms with level of 2 that follow a
  root term becomes its children (“narrower”); you can nest, i.e., have
  terms of level 3 below terms of level 2.  Note that this means the
  order of rows must be preserved in our CSV files: Do *not* sort them
  and then save them.
:label:
  This is a short, human-readable label for the term.  In the VO, this
  is generally derived fairly directly from subject, ususally by
  inserting blanks at the right places and fixing capitalisation.
:description:
  This is a longer explanation of what the term means.  We do not
  support any markup here, not even paragraphs, so there is probably a
  limit how much can be communicated here.
:more_relations:
  This column enables the declaration of non-hierarchical relationships
  and contains whitespace-separated declarations.  Each declaration has
  the form property[(term)].  See below for the common properties
  supported here.  Plain terms are references within the vocabulary, but
  CURIEs with known prefixes or full URIs are admitted, too.

Non-ASCII characters are allowed in label and description; files must be
in UTF-8.

It is recommended to have, in addition to the terms.csv, a README in
each vocabulary directory; this can contain internal notes, todo items,
backwards compatibility considerations, and the like.


Defining Vocabulary Metadata
============================

See Vocabularies in the VO 2, Appendix A.2.

In addition to what's there, in 2024-03, we're prototyping a
topconcepts key, which is a space-separated list of vocabulary terms
that should become objects in (vocab, skos:hasTopConcept, .) triples.


Deployment
==========

To have a local installation, decide on a location from where you'll
serve your vocabularies; since we currently generate apache .htaccess
files only, this should be served by an apache HTTP server.  Then, call
convert with its ``--root-uri`` set to where the tree will show up,
e.g.::

  python3 convert.py --root-uri http://localhost/rdf ALL
  python3 make-rdf-index.py build

In order for the .htaccess configuration to work, the toplevel directory
has to be configured to interpret FileInfo content in the apache
configuration.  This would look like this::

    <Directory /var/www/docs/rdf>
          AllowOverride FileInfo
          Options Indexes FollowSymLinks
    </Directory>

Also, mod_rewrite must be enabled.

If you are the administrator of the IVOA semantics repository, it is
recommended to work like this:

(1) Edit vocabs.conf, update the timestamp of the respective vocabulary to
    today (if applicable)
(2) Do the edit to the vocabulary source; don't forget the
    ivoasem:preliminary property on newly added terms.
(3) Run ``python3 convert.py <vocname>``, paying attention to any
    diagnostics.
(4) Inspect the files newly left in ``build`` as to whether they reflect
    the intended changes.
(5) Commit the result.  In the commit message, specify what caused
    the change ("mail by person@example.org"; "TCG telecon of 2020-02-11")
(6) Run ``sshfs semantics@ivoa.info:rdf ivoa-repo`` (you'll have to
    mkdir ``ivoa-repo`` if it doesn't exist yet, of course)
(7) Run ``python3 convert.py --dest-dir ivoa-repo <vocname>`` to update
    the vocabulary itself.
(8) Update the vocabulary index: ``python3 make-rdf-index.py ivoa-repo``
(9) Unmount the vocabulary repo: ``fusermount -u ivoa-repo``.
(10) Update https://wiki.ivoa.net/twiki/bin/view/IVOA/VEPs as
     appropriate.
(11) Run the validator from vocino2/validator on the new vocabulary:
     ``../vocinvo/validator/vocvalidator.py http://www.ivoa.net/rdf/...``

(Markus has a script rebuild.sh that does steps (6)-(9))
