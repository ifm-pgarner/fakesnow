from __future__ import annotations

from sqlglot import exp

MISSING_DATABASE = "missing_database"

# TODO: move this into a Dialect as a transpilation
def set_schema(expression: exp.Expression, current_database: str | None) -> exp.Expression:
    """Transform USE SCHEMA/DATABASE to SET schema.

    Example:
        >>> import sqlglot
        >>> sqlglot.parse_one("USE SCHEMA bar").transform(set_schema, current_database="foo").sql()
        "SET schema = 'foo.bar'"
        >>> sqlglot.parse_one("USE SCHEMA foo.bar").transform(set_schema).sql()
        "SET schema = 'foo.bar'"
        >>> sqlglot.parse_one("USE DATABASE marts").transform(set_schema).sql()
        "SET schema = 'marts.main'"

        See tests for more examples.
    Args:
        expression (exp.Expression): the expression that will be transformed.

    Returns:
        exp.Expression: A SET schema expression if the input is a USE
            expression, otherwise expression is returned as-is.
    """

    def transform_use(node: exp.Use, kind_name: str) -> exp.Command:
        assert node.this, f"No identifier for USE expression {node}"

        if kind_name == "DATABASE":
            # duckdb's default schema is main
            name = f"{node.this.name}.main"
        else:
            # SCHEMA
            if db := node.this.args.get("db"):
                db_name = db.name
            else:
                # isn't qualified with a database
                db_name = current_database or MISSING_DATABASE

            name = f"{db_name}.{node.this.name}"

        return exp.Command(this="SET", expression=exp.Literal.string(f"schema = '{name}'"))

    return expression.transform(
        lambda node: transform_use(node, kind.name.upper())
        if (
            isinstance(node, exp.Use)
            and (kind := node.args.get("kind"))
            and isinstance(kind, exp.Var)
            and kind.name
            and kind.name.upper() in ["SCHEMA", "DATABASE"]
        )
        else node,
    )


def as_describe(expression: exp.Expression) -> exp.Expression:
    """Prepend describe to the expression.

    Example:
        >>> import sqlglot
        >>> sqlglot.parse_one("SELECT name FROM CUSTOMERS").transform(as_describe).sql()
        'describe SELECT name FROM CUSTOMERS'
    Args:
        expression (exp.Expression): the expression that will be transformed.

    Returns:
        exp.Expression: The transformed expression.
    """

    return exp.Describe(this=expression)


# TODO: move this into a Dialect as a transpilation
def create_database(expression: exp.Expression) -> exp.Expression:
    """Transform create database to attach database.

    Example:
        >>> import sqlglot
        >>> sqlglot.parse_one("CREATE database foo").transform(create_database).sql()
        'ATTACH DATABASE ':memory:' as foo'
    Args:
        expression (exp.Expression): the expression that will be transformed.

    Returns:
        exp.Expression: The transformed expression.
    """

    def transform_create_db(node: exp.Create) -> exp.Command:
        assert (ident := node.find(exp.Identifier)), f"No identifier in {node.sql}"
        db_name = ident.this
        return exp.Command(
            this="ATTACH", expression=exp.Literal(this=f"DATABASE ':memory:' AS {db_name}", is_string=True)
        )

    return expression.transform(
        lambda node: transform_create_db(node)
        if isinstance(node, exp.Create) and str(node.args.get("kind")).upper() == "DATABASE"
        else node,
    )
