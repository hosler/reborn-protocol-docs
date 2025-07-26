Reborn Protocol Reference Documentation
========================================

Welcome to the comprehensive reference documentation for the Reborn protocol. This documentation provides detailed packet structure specifications, encoding formats, and implementation guidelines for developers working with Reborn servers and clients.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   protocol/overview
   protocol/packet-structures
   protocol/encryption
   protocol/data-types
   implementation/pyreborn-analysis
   implementation/conformance
   examples/usage

About This Documentation
========================

This documentation is derived from deep analysis of the GServer-v2 codebase and provides:

* Complete packet structure specifications
* Primitive-level encoding details for cross-language implementation
* ENCRYPT_GEN_5 protocol implementation details
* PyReborn library conformance analysis
* Implementation examples and best practices

The documentation is maintained as part of the OpenGraal2 project and is designed to enable developers to create compatible Graal clients and servers in any programming language.

Quick Start
===========

If you're new to the Reborn protocol, start with the :doc:`protocol/overview` section to understand the basic architecture, then move to :doc:`protocol/packet-structures` for detailed packet specifications.

For existing PyReborn users, see the :doc:`implementation/pyreborn-analysis` section for compatibility information and recommended fixes.

Contributing
============

This documentation is open source and contributions are welcome. The source is available on GitHub as part of the OpenReborn2 project.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`