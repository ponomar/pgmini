[![Test & Lint](https://github.com/ponomar/pgmini/actions/workflows/main.yml/badge.svg)](https://github.com/ponomar/pgmini/actions/workflows/main.yml)

## 🇺🇦 What is PGmini? 🇺🇦

It is the PostgreSQL query builder with next core principles:
- simple (predictable, without magic)
- fast

All object are immutable (thanks to [attrs](https://www.attrs.org) lib).
Python code as close to SQL structure as possible.
Library doesn't try to be everything.
It doesn't manage connections to postgres, doesn't escape params.
All this can and should be done with other tools: (asyncpg, psycopg2, ...).

I've decided to use `PascalCase` methods naming to avoid collisions with python reserved words: 
`From`, `And`, `Or`, `Else`, `With`, `As`, etc.

## Examples
```python
User = Table('user')  # dynamic columns

q = Select(User.id, User.name).From(User).Where(User.email == 'test@test.com')

build(q)
>>>
(
    'SELECT id, name FROM "user" WHERE email = $1', 
    ['test@test.com'],
)
```

Explicitly defined table schema allows to save filters and methods for further reusing 
and to use IDE code analyzers for smart completions, find usages, bulk refactors etc.  
```python
class RoleSchema(Table):
    id: int
    name: str
    status: str
    
    @property
    def status_active(self):  # can also be decorated with functools.cache
        return self.status == Literal('active')
    
    def name_like(self, value: str):
        return self.name.Like(f'%{value}%')

Role = RoleSchema('role')
q = Select(Role.id).From(Role).Where(Role.status_active, Role.name_like('adm'))

RoleAlias = Role.As('role2')  # all columns/methods are visible for IDE live inspection as well
q = (
    Select(Role.STAR).From(Role)
    .Where(Not(Exists(
        Select(1).From(RoleAlias)
        .Where(RoleAlias.id < Role.id, RoleAlias.status_active)
    )))
)
```

***

### Why not sqlalchemy?
- too smart (tries to do everything: from connection/session management, to sql generating and params escaping)
- too complex
- too slow
- mutable (on its core)

It is good for simple projects with simple sql queries. 
But when your project grows up, your team grows up, sqlalchemy always leads to errors,
unnecessary complexity, extra time your team need to spend to learn it, find not obvious bugs etc.  
It also pushes many people to write bad (not optimized) code.


### Why not pypika?
While it is much simpler then sqlalchemy, it also requires you to learn their own syntax 
and not always obvious how to write code without looking into the docs.
Its objects are also mutable which requires extra attention while writing code and leads to errors.


***

The library is inspired by Ukraine🇺🇦 (Kyiv is my home) and its brave and free people🔱.

Slava Ukraini, Heroyam slava!
