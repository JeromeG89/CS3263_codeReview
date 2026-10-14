"""Child process that executes one (possibly LLM-generated) Z3 script.

Protocol: the script must leave a z3 Solver in a variable named `s` such that
`s` is satisfiable iff a safety violation is possible. We call s.check() ourselves
and, if SAT, read back the values of the function parameters by *name* from the
model. Reads a JSON job on stdin, writes a JSON result on stdout. Never raises.
"""
import contextlib
import io
import json
import sys
import traceback


class _Stop(Exception):
    """Internal control flow (never raised by user scripts)."""


def _value(z3, v, signed_bits):
    if z3.is_bv_value(v):
        n = v.as_long()
        if signed_bits:
            w = v.size()
            if n >= 2 ** (w - 1):
                n -= 2**w
        return n
    if z3.is_int_value(v):
        return v.as_long()
    if z3.is_true(v):
        return 1
    if z3.is_false(v):
        return 0
    if z3.is_rational_value(v):
        return int(v.numerator_as_long() // v.denominator_as_long())
    raise ValueError(f"cannot convert model value {v}")


def _index(z3, sort, k):
    if sort.kind() == z3.Z3_BV_SORT:
        return z3.BitVecVal(k, sort.size())
    return z3.IntVal(k)


def _find_solver(z3, ns):
    for name in ("s", "solver"):
        if isinstance(ns.get(name), (z3.Solver, z3.Optimize)):
            return name, ns[name]
    cands = [(k, v) for k, v in ns.items() if isinstance(v, (z3.Solver, z3.Optimize))]
    if cands:
        return cands[-1]
    return None, None


def main():
    job = json.loads(sys.stdin.read())
    result = {"status": "error", "error_type": None, "error": "", "model": {}, "stdout": "",
              "solver_var": None, "num_assertions": None, "missing_params": []}
    try:
        import z3
    except Exception as exc:  # pragma: no cover
        result.update(error_type="env", error=repr(exc))
        print(json.dumps(result))
        return
    ns = {"__name__": "__main__"}
    out = io.StringIO()
    phase = "exec"
    try:
        exec("from z3 import *", ns)
        code = compile(job["code"], "<z3_script>", "exec")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(code, ns)
        phase = "check"
        name, s = _find_solver(z3, ns)
        if s is None:
            result.update(error_type="no_solver", error="script did not create a Solver named `s`")
            raise _Stop
        result["solver_var"] = name
        result["num_assertions"] = len(s.assertions())
        s.set("timeout", int(job.get("timeout_ms", 30000)))
        r = s.check()
        if r == z3.unsat:
            result["status"] = "unsat"
        elif r == z3.unknown:
            result.update(status="unknown", error_type="solver_unknown", error=str(s.reason_unknown()))
        else:
            result["status"] = "sat"
            m = s.model()
            decls = {}
            for d in m.decls():
                decls.setdefault(d.name(), d)
            scalars = {}
            for p in job["params"]:
                if p.get("array"):
                    continue
                d = decls.get(p["name"])
                if d is None or d.arity() != 0 or d.range().kind() == z3.Z3_ARRAY_SORT:
                    result["missing_params"].append(p["name"])
                    scalars[p["name"]] = 0  # unconstrained by the model: any value works
                    result["model"][p["name"]] = 0
                    continue
                scalars[p["name"]] = _value(z3, m[d], p.get("signed", True))
                result["model"][p["name"]] = scalars[p["name"]]
            for p in job["params"]:
                if not p.get("array"):
                    continue
                try:
                    n = int(eval(p["length_expr"], {"__builtins__": {}}, dict(scalars)))
                except Exception:  # noqa: BLE001
                    n = 0
                n = max(0, min(n, int(job.get("max_array", 65536))))
                d = decls.get(p["name"])
                if d is None or d.arity() != 0 or d.range().kind() != z3.Z3_ARRAY_SORT:
                    result["missing_params"].append(p["name"])
                    result["model"][p["name"]] = [0] * n
                    continue
                arr = d()
                dom = arr.domain()
                result["model"][p["name"]] = [
                    _value(z3, m.eval(arr[_index(z3, dom, k)], model_completion=True), p.get("signed", True))
                    for k in range(n)
                ]
    except _Stop:
        pass
    except SyntaxError as exc:
        result.update(error_type="syntax", error=f"SyntaxError: {exc.msg} (line {exc.lineno})")
    except z3.Z3Exception as exc:
        result.update(error_type="z3_api", error=f"Z3Exception: {exc}")
    except SystemExit as exc:
        result.update(error_type="runtime", error=f"script called exit({exc.code})")
    except BaseException as exc:  # noqa: BLE001
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tail = "".join(t for t in tb if "<z3_script>" in t or t is tb[-1])
        if isinstance(exc, NameError) and getattr(exc, "name", None):
            import difflib
            close = difflib.get_close_matches(exc.name, [n for n in dir(z3) if not n.startswith("_")], n=4, cutoff=0.6)
            tail += (f"Hint: `{exc.name}` does not exist in the z3 module." +
                     (f" Similar existing names: {', '.join(close)}" if close else ""))
        etype = "runtime" if phase == "exec" else "check_failed"
        if isinstance(exc, NameError):
            etype = "name_error"
        elif isinstance(exc, TypeError):
            etype = "type_error"
        result.update(error_type=etype, error=(tail or "".join(tb[-2:]))[-1500:])
    result["stdout"] = out.getvalue()[-2000:]
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
