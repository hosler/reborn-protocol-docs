# Reborn Protocol Documentation

[![Documentation Status](https://readthedocs.org/projects/reborn-protocol/badge/?version=latest)](https://reborn-protocol.readthedocs.io/en/latest/?badge=latest)

Comprehensive documentation for the Reborn protocol, providing detailed packet structure specifications, encoding formats, and implementation guidelines for developers working with Reborn servers and clients.

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
pip install -r requirements.txt

# Build docs
cd docs
make html

# View docs
open _build/html/index.html
```

## Online Documentation

The documentation is automatically built and hosted at: **https://reborn-protocol.readthedocs.io/**

## Contributing

This documentation is part of the OpenReborn2 project. Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This documentation is open source and available under the same license as the OpenReborn2 project.

## Related Projects

- **PyReborn** - Python client library for Reborn servers
- **GServer-v2** - Reference server implementation
- **OpenReborn2** - Complete Reborn game project