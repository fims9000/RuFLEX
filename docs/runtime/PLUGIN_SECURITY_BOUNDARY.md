# Plugin security boundary

RuFLEX does not accept uploaded Python code. Runtime plugins are installed
packages discovered only from the `ruflex.plugins` entry-point group during
startup. Descriptor identity, trusted status, duplicate keys and declared
optional dependencies are validated before the registry freezes.

Failures are typed (`RUNTIME_NOT_FOUND`, `RUNTIME_DUPLICATE`,
`RUNTIME_UNTRUSTED`, `RUNTIME_VERSION_MISMATCH`,
`RUNTIME_DEPENDENCY_MISSING`, `RUNTIME_INCOMPATIBLE`,
`RUNTIME_EXECUTION_FAILED`, `CAPABILITY_UNAVAILABLE`) and API clients receive
safe messages rather than tracebacks.

Plugins compute bounded requests only. They cannot persist independent project
state, change split roles, open final test, or tune policies.
