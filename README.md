[![Test & Lint](https://github.com/ponomar/pgmini/actions/workflows/main.yml/badge.svg)](https://github.com/ponomar/pgmini/actions/workflows/main.yml)

# 🇺🇦 pgmini 🇺🇦

PostgreSQL query builder with two core principles:
- **simple** — predictable, no magic, python code maps 1:1 to SQL structure
- **fast** — all objects are immutable (built on [attrs](https://www.attrs.org)), no heavy machinery

The library builds SQL strings and parameter lists — nothing else.
It doesn't manage connections, doesn't escape params, doesn't validate your schema.
Use it together with `asyncpg` / `psycopg` which do those jobs well.

All public methods use `PascalCase` (`From`, `Where`, `And`, `Else`, `With`, `As` ...)
to avoid collisions with python reserved words.

## Table of contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Core concepts](#core-concepts)
- [SELECT](#select)
- [Operations](#operations)
- [Logical operators](#logical-operators)
- [Functions](#functions)
- [CASE / ARRAY](#case--array)
- [INSERT](#insert)
- [UPDATE](#update)
- [DELETE](#delete)
- [Subqueries and CTE (WITH)](#subqueries-and-cte-with)
- [Row locking (FOR UPDATE)](#row-locking-for-update)
- [API cheat sheet](#api-cheat-sheet)

## Installation

```bash
pip install pgmini
```

## Quick start

```python
from pgmini import Select, Table, build

User = Table('user')  # columns are dynamic: User.<anything> is a column

q = Select(User.id, User.name).From(User).Where(User.email == 'test@test.com')

build(q)
# (
#     'SELECT id, name FROM "user" WHERE email = $1',
#     ['test@test.com'],
# )
```

## Core concepts

### build()

`build(query, driver='asyncpg')` compiles any statement to `(sql, params)`:
- `driver='asyncpg'` (default): placeholders `$1, $2, ...`, params is a `list`
- `driver='psycopg'`: placeholders `%(p1)s, %(p2)s, ...`, params is a `dict`

```python
build(Select(t.id).From(t).Where(t.id > 5))
# ('SELECT id FROM t WHERE id > $1', [5])

build(Select(t.id).From(t).Where(t.id > 5), driver='psycopg')
# ('SELECT id FROM t WHERE id > %(p1)s', {'p1': 5})
```

### Table and columns

`Table('name')` gives dynamic columns: any attribute access returns a column object.
`t.STAR` is `*`. Reserved names (`user`, `role`) are quoted automatically.
Column names are prefixed with the table name automatically when the query
references more than one table (multiple FROMs or JOINs).

```python
t = Table('t')
t.any_column          # t.any_column
t.STAR                # t.*
tx = t.As('x')        # aliased table: compiles to "t AS x", columns to "x.col"
```

All examples below assume `t = Table('t')`, `t2 = Table('t2')`.
Note: with a single table in FROM the prefix is omitted (`SELECT id FROM t`);
a standalone expression or a multi-table query gets prefixes (`t.id`).

A table schema can be defined explicitly — this enables IDE completion,
reusable filters and refactoring:

```python
class RoleSchema(Table):
    id: int
    name: str
    status: str

    @property
    def status_active(self):  # can also be decorated with functools.cache
        return self.status == Literal('active')

    def name_startswith(self, value: str):
        return self.name.Like(f'{value}%')

Role = RoleSchema('role')
q = Select(Role.id).From(Role).Where(Role.status_active, Role.name_startswith('admin'))
```

### Param / Literal / Raw

Any plain python value used inside a query becomes a **parameter** automatically.
Use wrappers only when you need extra behavior:

| Wrapper | Meaning | Example SQL |
|---|---|---|
| plain value | parameter (auto-wrapped) | `$1` |
| `Param(x)` | explicit parameter, allows `.Cast()` / `.As()` | `$1::int AS x` |
| `Literal(x)` | value inlined into SQL. **Not escaped — SQL injection risk, use only with 100% trusted data.** Supports int, float, str, bool, None, date, datetime and lists of those | `'abc'`, `15`, `ARRAY[1, 2]`, `NULL`, `TRUE` |
| `Raw('expr')` | raw SQL string inserted as is (e.g. to reference an alias) | `expr` |
| `NULL` | shortcut for `Literal(None)` | `NULL` |

```python
q = (
    Select(t.STAR, Param(10).Cast('int').As('added')).From(t)
    .Where(
        t.id1 == 1,
        t.id2 != Param(2).Cast('float'),
        t.id3 > Literal(3),
        t.id4 < Literal(4).Cast('numeric'),
    )
)
# SELECT *, $1::int AS added FROM t
# WHERE id1 = $2 AND id2 != $3::float AND id3 > 3 AND id4 < 4::numeric
# params: [10, 1, 2]
```

### Immutability

Every method returns a new object; the original is never modified.
Queries and expressions can be safely shared and extended:

```python
base = Select(t.id).From(t)
q1 = base.Where(t.status == 'active')  # base is unchanged
q2 = base.Where(t.status == 'deleted')
```

### Expression modifiers

Available on any expression (column, function, param, literal, operation, select):

| Method | SQL |
|---|---|
| `.Cast('int')` | `expr::int` (wraps in brackets when needed) |
| `.As('alias')` | `expr AS alias` |
| `.Distinct()` | `DISTINCT expr` |
| `.Asc()` / `.Desc()` | `expr ASC` / `expr DESC` (for ORDER BY) |
| `.NullsFirst()` / `.NullsLast()` | `expr NULLS FIRST` / `expr NULLS LAST` |

## SELECT

### Columns, FROM, WHERE

```python
Select(t.id, t.name).From(t)
# SELECT id, name FROM t

Select(t.STAR).From(t)
# SELECT * FROM t

Select(t.id).From(t).Where(t.name == 'x', t.age > 25)  # *args work as AND
# SELECT id FROM t WHERE name = $1 AND age > $2

q = Select(t.id).From(t).Where(t.id > 1)
q = q.Where(t.id < 10)  # chainable: filters are appended
# SELECT id FROM t WHERE id > $1 AND id < $2

Select(t.id).From(t).AddColumns(t.name, t.age)  # append columns to existing select
# SELECT id, name, age FROM t
```

`q.GetColumns()` returns a tuple of output column names (alias, column name or `None`):
useful to zip query results with names.

### JOIN

`Join` / `LeftJoin` / `JoinLateral` / `LeftJoinLateral`.
The ON condition can be any expression or `True` (compiles to `ON TRUE`).

```python
sq = Select(t2.name).From(t2).Where(t2.id == t.id).Subquery('sq')
q = (
    Select(t.id).From(t)
    .Join(t2, t2.id == t.id)
    .LeftJoin(t2, And(t2.id == t.id, t2.status == 'active'))
    .JoinLateral(sq, True)
    .LeftJoinLateral(sq, sq.name != 'test')
)
# SELECT t.id FROM t
# JOIN t2 ON t2.id = t.id
# LEFT JOIN t2 ON t2.id = t.id AND t2.status = $1
# JOIN LATERAL (SELECT name FROM t2 WHERE id = t.id) AS sq ON TRUE
# LEFT JOIN LATERAL (SELECT name FROM t2 WHERE id = t.id) AS sq ON sq.name != $2
# params: ['active', 'test']
```

### Table-series join (FROM table, UNNEST(...))

A function can be used as a FROM item alongside tables.
Give it an alias with a column list `x(col)` and reference its columns as attributes:

```python
f = F.unnest(t.tags).As('x(tag)')
Select(t.id, f.tag).From(t, f)
# SELECT t.id, x.tag FROM t, UNNEST(t.tags) AS x(tag)

f = F.unnest(Param([1, 2]).Cast('int[]'), Param(['a', 'b']).Cast('text[]')).As('x(a, b)')
Select(f.a, f.b).From(f)
# SELECT a, b FROM UNNEST($1::int[], $2::text[]) AS x(a, b)
```

### GROUP BY / HAVING

```python
Select(F.count('*')).From(t).GroupBy(t.status).Having(F.count('*') > 10)
# SELECT COUNT(*) FROM t GROUP BY status HAVING COUNT(*) > $1

# GROUP BY by output alias — use Raw
Select(t.id.As('xyz')).From(t).GroupBy(Raw('xyz'))
# SELECT id AS xyz FROM t GROUP BY xyz
```

`GroupBy` can be set only once; `Having` is chainable (works as AND).

### ORDER BY / LIMIT / OFFSET

```python
Select(t.STAR).From(t).OrderBy(t.id.Desc(), t.name.NullsLast())
# SELECT * FROM t ORDER BY id DESC, name NULLS LAST

Select(t.id).From(t).OrderBy(t.id).OrderBy(t.age)  # chainable: appended
# SELECT id FROM t ORDER BY id, age

q.OrderBy(None)   # removes ORDER BY
q.Limit(10)       # LIMIT $n  (value becomes a param; Literal(10) inlines it)
q.Limit(None)     # removes LIMIT
q.Offset(20)      # OFFSET $n
q.Offset(None)    # removes OFFSET
```

### DISTINCT / DISTINCT ON

```python
Select(t.id.Distinct()).From(t)
# SELECT DISTINCT id FROM t

Select(t.id, t.status).From(t).DistinctOn(t.status)
# SELECT DISTINCT ON (status) id, status FROM t
```

### UNION / INTERSECT / EXCEPT

`Union` / `UnionAll` / `Intersect` / `Except`, chainable:

```python
Select(t.id).From(t).Union(Select(t2.id).From(t2))
# SELECT id FROM t UNION SELECT id FROM t2

Select(Literal('x')).Union(Select(Literal('a'))).UnionAll(Select(Literal('b')))
# SELECT 'x' UNION SELECT 'a' UNION ALL SELECT 'b'
```

To ORDER BY / LIMIT the combined result, wrap the union into a subquery
and apply them outside.

### Scalar subquery as a column

A `Select` used as a column is wrapped in brackets automatically:

```python
Select(t.id, Select(t2.id).From(t2).Where(t2.id == t.id).As('other')).From(t)
# SELECT id, (SELECT id FROM t2 WHERE id = t.id) AS other FROM t
```

## Operations

Math operators work natively: `+`, `-`, `*`, `/`, `>`, `>=`, `<`, `<=`, `==`, `!=`.
`== None/True/False` compiles to `IS`; `!=` to `IS NOT`.
Everything else is a method:

| Python | SQL |
|---|---|
| `t.col == 1` / `t.col != 1` | `col = $1` / `col != $1` |
| `t.col == None` | `col IS $1` (use `t.col == NULL` for `col IS NULL`) |
| `t.col.Is(None)` / `t.col.IsNot(False)` | `col IS $1` / `col IS NOT $1` |
| `t.col.In([1, 2, 3])` | `col IN ($1, $2, $3)` |
| `t.col.In(Select(...))` | `col IN (SELECT ...)` |
| `t.col.NotIn(...)` | `col NOT IN (...)` |
| `t.col.Any([1, 2])` | `col = ANY($1)` — single param, faster plan cache than IN |
| `t.col.LikeAny(['a%', '%b'])` | `col LIKE ANY($1)` |
| `t.col.IlikeAny(Literal(['%a%']))` | `col ILIKE ANY(ARRAY['%a%'])` |
| `t.col.Between(1, 2)` | `col BETWEEN $1 AND $2` |
| `t.col.Like('%x%')` / `t.col.Ilike('%x%')` | `col LIKE $1` / `col ILIKE $1` |
| `t.col.Op('->>', 'key')` | `col ->> $1` — any custom operator |
| `t.col[1]` | `col[$1]` — array index |
| `t.col[2:5]`, `t.col[:5]`, `t.col[4:]` | `col[$1:$2]` — array slice |

```python
t.data.Op('#>', ['k1', 'k2'])              # t.data #> $1
t.dt.Op('at time zone', 'UTC')             # t.dt at time zone $1
t.col[3:F.array_length(t.col, 1)]          # t.col[$1:ARRAY_LENGTH(t.col, $2)]
(t.id == 10).As('is_ten')                  # (t.id = $1) AS is_ten
```

Operations compose: any operation result is itself an expression and supports
`.Cast()`, `.As()`, comparison, chaining etc.

## Logical operators

```python
from pgmini import And, Or, Not, Exists

Select(t.id).From(t).Where(
    t.id.Between(10, 20),
    Or(t.name > 'name', And(t.status == 'active', Not(t.id == 15))),
)
# SELECT id FROM t
# WHERE id BETWEEN $1 AND $2 AND (name > $3 OR (status = $4 AND NOT (id = $5)))

Select(t.STAR).From(t).Where(Not(Exists(
    Select(1).From(t2).Where(t2.id == t.id)
)))
# SELECT * FROM t WHERE NOT (EXISTS (SELECT $1 FROM t2 WHERE id = t.id))
```

## Functions

`F` (alias `Func`) builds any function dynamically — `F.<name>(*args)` compiles to
`NAME(args)`. There is no allowlist: any function name works.

```python
F.now()                      # NOW()
F.count('*')                 # COUNT(*)
F.count(t.id.Distinct())     # COUNT(DISTINCT t.id)
F.date_trunc(Literal('day'), t.created)  # DATE_TRUNC('day', t.created)
```

### Window functions: OVER

```python
F.row_number().Over()                                   # ROW_NUMBER() OVER ()
F.count(t.id).Over(partition_by=t.name, order_by=t.age.Desc())
# COUNT(t.id) OVER (PARTITION BY t.name ORDER BY t.age DESC)
```

`partition_by` / `order_by` take a single expression or an iterable of them.

### Aggregates: FILTER, ORDER BY, WITHIN GROUP

```python
F.count('*').Where(t.id > 10)                # COUNT(*) FILTER (WHERE t.id > $1)
F.array_agg(t.id).OrderBy(t.id.Desc())       # ARRAY_AGG(t.id ORDER BY t.id DESC)

F.percentile_disc(t.fld).WithinGroup(t.fld2)
# PERCENTILE_DISC(t.fld) WITHIN GROUP (ORDER BY t.fld2)

F.percentile_cont(Literal(0.5)).WithinGroup(t.fld2.Desc()).As('p50')
# PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.fld2 DESC) AS p50
```

### Function as a FROM item

```python
f = F.unnest(Literal([1, 2, 3])).As('idx')
Select(f.STAR).From(f)
# SELECT * FROM UNNEST(ARRAY[1, 2, 3]) AS idx
```

See also [table-series join](#table-series-join-from-table-unnest).

## CASE / ARRAY

```python
from pgmini import Case, Array, Tuple

Select(Case((t.id == 1, 'first'), (t.id == 2, 'second'), Else='third').As('val')).From(t)
# SELECT CASE WHEN id = $1 THEN $2 WHEN id = $3 THEN $4 ELSE $5 END AS val FROM t

Select(Array([t.id, 5, 7])).From(t)   # SELECT ARRAY[id, $1, $2] FROM t
Tuple([t.id, 5])                      # (t.id, $1)
```

## INSERT

`Insert(table, columns)` — columns are required (strings or column objects).

```python
from pgmini import Insert

q = (
    Insert(t, columns=(t.name, t.status))
    .Values(
        (Param('some text').Cast('varchar(10)'), 'active'),
        ('other text', Literal('deleted')),
    )
    .Returning(t.STAR)
)
# INSERT INTO t (name, status)
# VALUES ($1::varchar(10), $2), ($3, 'deleted')
# RETURNING t.*
```

### INSERT ... SELECT

```python
q = (
    Insert(t, columns=(t.name, t.status))
    .Select(Select(t.name, t.status).From(t).Where(t.id < 100).Limit(10))
)

# efficient bulk insert of python lists via UNNEST:
values = [(str(i), 'active') for i in range(1_000)]
q = Insert(t, ('name', 'status')).Select(Select(
    F.unnest(Param([name for name, _ in values]).Cast('text[]')),
    F.unnest(Param([status for _, status in values]).Cast('enum_status[]')),
))
# INSERT INTO t (name, status) SELECT UNNEST($1::text[]), UNNEST($2::enum_status[])
```

### ON CONFLICT

`OnConflict(*, constraint=None, index_elements=None, index_where=None, do_update=None, do_nothing=False)`.
Exactly one of `do_update` / `do_nothing` is required.
`Excluded('col')` / `Excluded(t.col)` references the excluded row in `do_update`.

```python
from pgmini import Excluded

Insert(t, (t.id,)).OnConflict(do_nothing=True)
# INSERT INTO t (id) ON CONFLICT DO NOTHING

Insert(t, (t.id,)).OnConflict(constraint='cc_uniq', do_nothing=True)
# INSERT INTO t (id) ON CONFLICT ON CONSTRAINT cc_uniq DO NOTHING

Insert(t, (t.id,)).OnConflict(
    index_elements=(t.id,), index_where=t.id > 0, do_nothing=True,
)
# INSERT INTO t (id) ON CONFLICT (id) WHERE id > $1 DO NOTHING

Insert(t, (t.id,)).OnConflict(do_update={
    'col1': 12,
    t.col2: t.col2 + 5,
    t.col3: Excluded('col8').Cast('int') * 88,
})
# INSERT INTO t (id) ON CONFLICT DO UPDATE
# SET col1 = $1, col2 = t.col2 + $2, col3 = excluded.col8::int * $3
```

## UPDATE

```python
from pgmini import Update

Update(t).Set({t.name: 'second'}).Where(t.name == 'first').Returning(t.id)
# UPDATE t SET name = $1 WHERE t.name = $2 RETURNING t.id

Update(t).Set({t.status: t2.status}).From(t2).Where(t2.id == t.id)
# UPDATE t SET status = t2.status FROM t2 WHERE t2.id = t.id
```

`Set` takes a dict (keys: column objects or strings). `Where` is chainable (AND).

## DELETE

```python
from pgmini import Delete

Delete(t).Where(t.id == 25).Returning(t.id)
# DELETE FROM t WHERE t.id = $1 RETURNING t.id
```

## Subqueries and CTE (WITH)

Any `Select` / `Insert` / `Update` / `Delete` has a `.Subquery(alias, materialized=False)` method.
The result object exposes its columns as attributes.

```python
sq = Select(t.id).From(t).Where(t.id < 100).Subquery('sq')

# as a subquery in FROM:
Select(sq.id).From(sq).Where(sq.id > 50)
# SELECT id FROM (SELECT id FROM t WHERE id < $1) AS sq WHERE id > $2

# as a CTE:
With(sq).Select(sq.id).From(sq).Where(sq.id > 50)
# WITH sq AS (SELECT id FROM t WHERE id < $1) SELECT id FROM sq WHERE id > $2
```

`With(*subqueries)` accepts several CTEs and starts any statement type:
`.Select(...)`, `.Insert(table, columns)`, `.Update(table)`, `.Delete(table)`.

```python
x1 = Select(t.id).From(t).Subquery('x1', materialized=True)
x2 = Select(t2.id).From(t2).Subquery('x2')
With(x1, x2).Select(x1.id, x2.id.As('id2')).From(x1, x2).Where(x1.id == x2.id)
# WITH x1 AS MATERIALIZED (SELECT id FROM t),
# x2 AS (SELECT id FROM t2)
# SELECT x1.id, x2.id AS id2 FROM x1, x2 WHERE x1.id = x2.id

# writable CTE:
sq = Update(t).Set({t.id: t.id2}).Returning(t.id).Subquery('sq')
With(sq).Select(F.count('*')).From(sq)
# WITH sq AS (UPDATE t SET id = t.id2 RETURNING t.id) SELECT COUNT(*) FROM sq
```

## Row locking (FOR UPDATE)

`Select.ForUpdate(*, of=None, nowait=False, skip_locked=False)`:
- `of` — lock only rows of the given table(s): a table/alias or an iterable of them
- `nowait=True` — error immediately instead of waiting for a lock
- `skip_locked=True` — skip already locked rows
- `nowait` and `skip_locked` are mutually exclusive (raises `ValueError`)

```python
Select(t.id).From(t).ForUpdate()
# SELECT id FROM t FOR UPDATE

Select(t.id).From(t).ForUpdate(skip_locked=True)
# SELECT id FROM t FOR UPDATE SKIP LOCKED

Select(t.id).From(t).ForUpdate(nowait=True)
# SELECT id FROM t FOR UPDATE NOWAIT

t2a = t2.As('x')
Select(t.id).From(t, t2a).ForUpdate(of=(t, t2a), skip_locked=True)
# SELECT t.id FROM t, t2 AS x FOR UPDATE OF t, x SKIP LOCKED

# typical work-queue pattern with CTE:
sq = Select(t.id).From(t).Limit(1).ForUpdate(skip_locked=True).Subquery('sq')
With(sq).Update(t).Set({t.status: 'processing'}).Where(t.id == sq.id)
# WITH sq AS (SELECT id FROM t LIMIT $1 FOR UPDATE SKIP LOCKED)
# UPDATE t SET status = $2 WHERE t.id = sq.id
```

## API cheat sheet

Compact reference of the whole public API (`from pgmini import ...`):

```text
build(query, driver='asyncpg'|'psycopg') -> (sql, params)

Table(name) -> table; .As(alias); .STAR; .<attr> -> column
Select(*columns)
    .From(*tables) .Join/LeftJoin/JoinLateral/LeftJoinLateral(item, on)
    .Where(*exprs) .GroupBy(*exprs) .Having(*exprs)
    .OrderBy(*exprs|None) .Limit(v|None) .Offset(v|None)
    .Distinct via column.Distinct() / .DistinctOn(*exprs)
    .Union/UnionAll/Intersect/Except(select)
    .ForUpdate(of=None, nowait=False, skip_locked=False)
    .AddColumns(*exprs) .GetColumns() .As(alias) .Cast(type)
    .Subquery(alias, materialized=False)
Insert(table, columns) .Values(*rows) .Select(select)
    .OnConflict(constraint=, index_elements=, index_where=, do_update=, do_nothing=)
    .Returning(*exprs) .Subquery(alias)
Update(table) .Set(dict) .From(*tables) .Where(*exprs) .Returning(*exprs) .Subquery(alias)
Delete(table) .Where(*exprs) .Returning(*exprs) .Subquery(alias)
With(*subqueries) .Select(...) / .Insert(table, columns) / .Update(table) / .Delete(table)

Param(value)    -> $1 / %(p1)s
Literal(value)  -> inlined (int/float/str/bool/None/date/datetime/list); NULL = Literal(None)
Raw('sql')      -> inserted as is
F.<name>(*args) -> function; .Over(partition_by=, order_by=) .Where(*filter_exprs)
                   .OrderBy(*exprs) .WithinGroup(*order_exprs) .As('x(a, b)') for FROM usage
Case((cond, value), ..., Else=default)
Array([...]) / Tuple([...])
And(*exprs) / Or(*exprs) / Not(expr) / Exists(select)
Excluded(col) — excluded.* reference for ON CONFLICT DO UPDATE

expression methods (any column/param/literal/function/operation/select):
    == != > >= < <= + - * /  [idx] [start:stop]
    .Is(x) .IsNot(x) .In(seq|select) .NotIn(seq|select)
    .Any(seq|expr) .LikeAny(seq|expr) .IlikeAny(seq|expr)
    .Between(a, b) .Like(x) .Ilike(x) .Op('operator', x)
    .Cast(type) .As(alias) .Distinct() .Asc() .Desc() .NullsFirst() .NullsLast()
```

Notes for query generation:
- plain python values become parameters; `Literal` inlines; `Raw` is verbatim
- column names get table prefixes automatically when >1 table is referenced
- `Where`, `Having`, `OrderBy` are chainable and append; `GroupBy` can be set once
- every method returns a new immutable object

***

### Why not sqlalchemy?
- too smart (tries to do everything: from connection/session management, to sql generating and params escaping)
- too complex
- too slow
- mutable (on its core)

It is good for simple projects with simple sql queries.
But when your project grows up, your team grows up, sqlalchemy always leads to errors,
unnecessary complexity, extra time your team need to spend to learn it, find not obvious bugs etc.

### Why not pypika?
While it is much simpler then sqlalchemy, it also requires you to learn their own "sql syntax" which is not always obvious.
And by default it uses parameters as literals, so it can lead to sql injections.

***

The library is inspired by Ukraine🇺🇦 (Kyiv is my home) and its brave and free people🔱.

Slava Ukraini, Heroyam slava!
