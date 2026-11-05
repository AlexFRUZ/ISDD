from __future__ import annotations

import ast
import io
import tokenize

DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
MULTILINE_STARTS = {getattr(tokenize, name) for name in ("FSTRING_START", "TSTRING_START") if hasattr(tokenize, name)}
MULTILINE_ENDS = {getattr(tokenize, name) for name in ("FSTRING_END", "TSTRING_END") if hasattr(tokenize, name)}


def _docstring(node: ast.AST) -> ast.Expr | None:
    body = getattr(node, "body", None)
    if not body or not isinstance(body[0], ast.Expr):
        return None
    value = body[0].value
    return body[0] if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _tokens(source: str) -> list[tokenize.TokenInfo]:
    return list(tokenize.generate_tokens(io.StringIO(source).readline))


def _protected_rows(tokens: list[tokenize.TokenInfo]) -> set[int]:
    rows: set[int] = set()
    opened: list[int] = []
    for token in tokens:
        if token.type == tokenize.STRING and token.start[0] != token.end[0]:
            rows.update(range(token.start[0], token.end[0] + 1))
        elif token.type in MULTILINE_STARTS:
            opened.append(token.start[0])
        elif token.type in MULTILINE_ENDS:
            rows.update(range(opened.pop(), token.end[0] + 1))
    return rows


def clean_python(source: str) -> str:
    tree = ast.parse(source)
    tokens = _tokens(source)
    lines = source.splitlines(keepends=True)
    removed: set[int] = set()
    after_docstring: set[int] = set()
    replaced: dict[int, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, DOCSTRING_OWNERS):
            continue
        docstring = _docstring(node)
        if docstring is None:
            continue
        rows = range(docstring.lineno, docstring.end_lineno + 1)
        removed.update(rows)
        if len(node.body) == 1 and not isinstance(node, ast.Module):
            replaced[docstring.lineno] = " " * docstring.col_offset + "pass\n"
        else:
            after_docstring.add(docstring.end_lineno + 1)

    protected = _protected_rows(tokens) - removed
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        row, column = token.start
        before = lines[row - 1][:column]
        if before.strip():
            lines[row - 1] = before.rstrip() + "\n"
        else:
            removed.add(row)

    output: list[tuple[int, str]] = []
    skip_blank = False
    for row, line in enumerate(lines, start=1):
        if row in after_docstring:
            skip_blank = True
        if row in replaced:
            output.append((row, replaced[row]))
            continue
        if row in removed:
            continue
        if skip_blank and not line.strip():
            continue
        skip_blank = False
        output.append((row, line))

    result: list[str] = []
    blanks = 0
    for row, line in output:
        if not line.strip() and row not in protected:
            blanks += 1
            if blanks > 2 or not result:
                continue
        else:
            blanks = 0
        result.append(line)
    return "".join(result).rstrip() + "\n"
