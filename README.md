# Reborn Protocol Documentation

[![Documentation Status](https://readthedocs.org/projects/reborn-protocol-docs/badge/?version=latest)](https://reborn-protocol-docs.readthedocs.io/en/latest/?badge=latest)

This documentation gives developers detailed packet structure specifications
and encoding formats for the Reborn protocol. It also gives implementation
guidelines for Reborn servers and clients.

## Documentation Contents

- **Protocol Overview** - Architecture and core concepts
- **Packet Structures** - Complete packet reference with encoding details
- **Encryption Details** - ENCRYPT_GEN_5 implementation specifics
- **Data Types** - Primitive-level encoding specifications
- **Implementation Analysis** - PyReborn conformance and recommendations
- **Usage Examples** - Practical implementation examples

## Features

- 🔍 **Complete Packet Catalog** - 100+ documented packet types
- 🔢 **Primitive-Level Encoding** - Cross-language implementation support
- 🔐 **Encryption Specifications** - Exact GEN_5 algorithm details
- 📊 **Conformance Analysis** - PyReborn compatibility assessment
- 💻 **Code Examples** - Python, JavaScript, and C++ implementations

## Quick Start

1. **New to Reborn Protocol?** Start with [Protocol Overview](docs/protocol/overview.md)
2. **Need Packet Details?** See [Packet Structures](docs/protocol/packet-structures.md)
3. **Using PyReborn?** Check [PyReborn Analysis](docs/implementation/pyreborn-analysis.md)

## Building Documentation

```bash
# Install dependencies
/usr/bin/python3.13 -m pip install -r requirements.txt

# Build docs
/usr/bin/python3.13 -m sphinx -b html docs _build/html

# View docs
open _build/html/index.html
```

Use `/usr/bin/python3.13` for repository tests and documentation tooling. The
system `python3` is 3.14 and does not have Hypothesis installed.

## Online Documentation

The build system automatically builds and hosts the documentation at
**https://reborn-protocol-docs.readthedocs.io/**.

## Citation guard

These docs cite source by `path/to/file.py:123` in about 640 places. A refactor
in another repo invalidates those citations silently, because nothing connects
the two. That is how 65 citations went dead at once when `gs1_client.py`,
`gs2_client.py`, `game/gs2_gui.py` and `packets.py` each became a package.

`scripts/check_doc_citations.py` resolves every citation it can and fails on the
ones that rot. Run it from anywhere in the checkout:

```bash
python3 scripts/check_doc_citations.py            # exit 1 on a dead citation
python3 scripts/check_doc_citations.py --verbose  # also list what it skipped
```

It needs the sibling repos (`pyReborn`, `reborn-protocol`, and the third-party
checkouts) beside this one, and it exits quietly when it cannot find them. A
citation it cannot resolve without guessing is reported, never failed.

To run it on every commit, symlink the chained hook into each repo. That hook
also runs the prose lint, so it replaces an existing `pre-commit` rather than
conflicting with it:

```bash
ln -sfn "$PWD/scripts/pre-commit" ../pyReborn/.git/hooks/pre-commit
ln -sfn "$PWD/scripts/pre-commit" ../reborn-protocol/.git/hooks/pre-commit
ln -sfn "$PWD/scripts/pre-commit" .git/hooks/pre-commit
```

`git config doccite.block false` downgrades the guard to a warning.

## Contributing

This documentation is part of the OpenReborn2 project. The project welcomes
contributions.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

The OpenReborn2 project makes this documentation available under the same
open-source license as the project.

## Related Projects

- **PyReborn** - Python client library for Reborn servers
- **GServer-v2** - Reference server implementation
- **OpenReborn2** - Complete Reborn game project
