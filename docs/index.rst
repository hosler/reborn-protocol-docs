Reborn Protocol Reference Documentation
========================================

Welcome to the comprehensive reference documentation for the Reborn protocol. This documentation provides detailed packet structure specifications, encoding formats, and implementation guidelines for developers working with Reborn servers and clients.

.. note::

   New to the protocol? Start with :doc:`protocol/overview` to understand why everything adds 32, why there are three string types, and other architectural decisions from the late 1990s.

.. toctree::
   :maxdepth: 2
   :caption: Protocol Specification:

   protocol/overview
   protocol/data-types
   protocol/strings
   protocol/encryption
   protocol/packet-structures
   protocol/gserver-behavior
   protocol/level-link-implementation
   protocol/serverside-behavior

.. toctree::
   :maxdepth: 2
   :caption: Implementation:

   implementation/pyreborn-analysis
   implementation/pyreborn-gaps
   implementation/conformance
   examples/usage

About This Documentation
========================

This documentation is derived from deep analysis of the GServer-v2 codebase and provides:

* Complete packet structure specifications (100+ packets documented)
* Primitive-level encoding details for cross-language implementation
* The infamous G-type encoding explained with visual diagrams
* The three string types (yes, three) and their gotchas
* ENCRYPT_GEN_5 protocol implementation with flow diagrams
* PyReborn library conformance analysis
* Implementation examples in Python, JavaScript, and C++

The documentation is maintained as part of the OpenGraal2 project and is designed to enable developers to create compatible Graal clients and servers in any programming language.

Reading Order
=============

For newcomers to the Reborn protocol:

1. :doc:`protocol/overview` - The big picture and common pitfalls
2. :doc:`protocol/data-types` - G-type encoding (the +32 obsession)
3. :doc:`protocol/strings` - The three string types and the PLO_LEVELLINK trap
4. :doc:`protocol/encryption` - Packet bundling, compression, and "encryption"
5. :doc:`protocol/packet-structures` - Individual packet formats

For existing developers:

* :doc:`protocol/gserver-behavior` - How GServer-v2 actually implements things
* :doc:`implementation/pyreborn-analysis` - Conformance issues and fixes

Contributing
============

This documentation is open source and contributions are welcome. The source is available on GitHub as part of the OpenGraal2 project.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
