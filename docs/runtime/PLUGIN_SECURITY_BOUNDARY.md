# Plugin security boundary

RuFLEX does not accept uploaded Python code. Runtime plugins are installed
packages discovered at startup from category-specific entry-point groups:
`ruflex.plugins`/`ruflex.model_adapters`, `ruflex.explainers`,
`ruflex.validators`, and `ruflex.execution_backends`. Descriptor identity,
duplicate keys, declared optional dependencies, and the complete typed adapter
contract are validated before the registry freezes. Installed packages are a
local trust boundary; the public runtime catalog never loads code supplied by a
project or API request.

Failures are typed (`RUNTIME_NOT_FOUND`, `RUNTIME_DUPLICATE`,
`RUNTIME_UNTRUSTED`, `RUNTIME_VERSION_MISMATCH`,
`RUNTIME_DEPENDENCY_MISSING`, `RUNTIME_INCOMPATIBLE`,
`RUNTIME_EXECUTION_FAILED`, `CAPABILITY_UNAVAILABLE`) and API clients receive
safe messages rather than tracebacks.

Plugins compute bounded requests only. They cannot persist independent project
state, change split roles, open final test, or tune policies.
