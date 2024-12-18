"""
read the ucd-list.txt as from the UCDList EN and make a CSV for
vocabulary tooling out of it.

This is based on the parsing script in the EN source.
"""


def convert_line(line):
    pieces = line.split('|')
    if len(pieces) == 3:
        return [s.strip() for s in pieces]
    else:
        # if it didn't parse, it was not in the normative EN list either,
        # and so we skip it, too.
        pass


def ucd_to_csv(in_file):
    for cur_line in in_file:
        if cur_line.startswith("#"):
            continue
        syncode, word, description = convert_line(cur_line)
        assert '"' not in description
        print(f"{word};1;{word};\"{description}\";"
            f"ivoasem:UCDSyntaxCode(`{syncode})")

if __name__ == '__main__':
    with open("ucd-list.txt", 'r') as f:
        ucd_to_csv(f)
