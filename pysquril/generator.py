
import json

from typing import Union, Callable, Optional

from pysquril.parser import (
    Key,
    ArraySpecific,
    ArraySpecificSingle,
    ArraySpecificMultiple,
    ArrayBroadcastSingle,
    ArrayBroadcastMultiple,
    SelectTerm,
    WhereTerm,
    OrderTerm,
    RangeTerm,
    Clause,
    UriQuery,
)

class SqlGenerator(object):

    """
    Generic class, used to implement SQL code generation.

    """

    db_init_sql = None
    json_array_sql = None

    def __init__(
        self,
        table_name: str,
        uri_query: str,
        data: Union[list, dict] = None,
    ) -> None:
        self.table_name = table_name
        self.uri_query = uri_query
        self.data = data
        self.parsed_uri_query = UriQuery(table_name, uri_query)
        self.operators = {
            'eq': '=',
            'gt': '>',
            'gte': '>=',
            'lt': '<',
            'lte': '<=',
            'neq': '!=',
            'like': 'like',
            'ilike': 'ilike',
            'not': 'not',
            'is': 'is',
            'in': 'in'
        }
        if not self.json_array_sql:
            msg = 'Extending the SqlGenerator requires setting the class level property: json_array_sql'
            raise Exception(msg)
        self.select_query = self.sql_select()
        self.update_query = self.sql_update()
        self.delete_query = self.sql_delete()

    # Classes that extend the SqlGenerator must implement the following methods
    # they are called by functions that are mapped over terms in clauses
    # for each term, an appropriate piece of SQL needs to be returned.
    # What is appropriate, depends on the backend.

    def _gen_sql_key_selection(self, term: SelectTerm, parsed: Key) -> str:
        """
        Generate SQL for selecting a Key element.

        Called by _term_to_sql_select when generating the select
        part of the SQL.

        """
        raise NotImplementedError

    def _gen_sql_array_selection(self, term: SelectTerm, parsed: ArraySpecific) -> str:
        """
        Generate SQL for selecting an ArraySpecific element.

        Called by _term_to_sql_select when generating the select
        part of the SQL.

        """
        raise NotImplementedError

    def _gen_sql_array_sub_selection(
        self,
        term: SelectTerm,
        parsed: Union[
            ArraySpecificSingle,
            ArraySpecificMultiple,
            ArrayBroadcastSingle,
            ArrayBroadcastMultiple,
        ],
    ) -> str:
        """
        Generate SQL for selecting inside arrays.

        Called by _term_to_sql_select when generating the select
        part of the SQL.

        """
        raise NotImplementedError

    def _gen_sql_col(self, term: Union[SelectTerm, WhereTerm, OrderTerm]) -> str:
        """
        Generate a column reference from a term,
        used in where and order clauses.

        """
        raise NotImplementedError

    def _gen_sql_update(self, term: Key) -> str:
        """
        Generate an update expression, from a term
        using the data passed to the constructor.

        """
        raise NotImplementedError

    def _clause_map_terms(self, clause: Clause, map_func: Callable) -> list:
        # apply a function to all Terms in a clause
        out = []
        for term in clause.parsed:
            res = map_func(term)
            out.append(res)
        return out

    # methods for mapping functions over terms in different types of clauses

    def select_map(self, map_func: Callable) -> Optional[list]:
        return self._clause_map_terms(self.parsed_uri_query.select, map_func) \
            if self.parsed_uri_query.select else None

    def where_map(self, map_func: Callable) -> Optional[list]:
        return self._clause_map_terms(self.parsed_uri_query.where, map_func) \
            if self.parsed_uri_query.where else None

    def order_map(self, map_func: Callable) -> Optional[list]:
        return self._clause_map_terms(self.parsed_uri_query.order, map_func) \
            if self.parsed_uri_query.order else None

    def range_map(self, map_func: Callable) -> Optional[list]:
        return self._clause_map_terms(self.parsed_uri_query.range, map_func) \
            if self.parsed_uri_query.range else None

    def set_map(self, map_func: Callable) -> Optional[list]:
        return self._clause_map_terms(self.parsed_uri_query.set, map_func) \
            if self.parsed_uri_query.set else None

    # term handler functions
    # mapped over terms in a clause
    # generates SQL for each term
    # SQL is generated by calling other functions
    # which are implemented for specific SQL backend implementations

    def _term_to_sql_select(self, term: SelectTerm) -> str:
        rev = term.parsed.copy()
        rev.reverse()
        out = []
        first_done = False
        for parsed in rev:
            if isinstance(parsed, Key):
                if not first_done:
                    selection = self._gen_sql_key_selection(term, parsed)
            elif isinstance(parsed, ArraySpecific):
                selection = self._gen_sql_array_selection(term, parsed)
            elif (
                isinstance(parsed, ArraySpecificSingle)
                or isinstance(parsed, ArraySpecificMultiple)
                or isinstance(parsed, ArrayBroadcastSingle)
                or isinstance(parsed, ArrayBroadcastMultiple)
            ):
                selection = self._gen_sql_array_sub_selection(term, parsed)
            else:
                raise Exception(f'Could not parse {term.original}')
            first_done = True
        return selection

    def _term_to_sql_where(self, term: WhereTerm) -> str:
        groups_start = ''.join(term.parsed[0].groups_start)
        groups_end = ''.join(term.parsed[0].groups_end)
        combinator = term.parsed[0].combinator if term.parsed[0].combinator else ''
        col = self._gen_sql_col(term)
        op = term.parsed[0].op
        val = term.parsed[0].val
        try:
            int(val)
            val = f'{val}'
        except ValueError:
            if val == 'null' or op == 'in':
                val = f'{val}'
            else:
                val = f"'{val}'"
        if op.endswith('.not'):
            op = op.replace('.', ' ')
        elif op.startswith('not.'):
            op = op.replace('.', ' ')
        elif op == 'in':
            val = val.replace('[', '')
            val = val.replace(']', '')
            values = val.split(',')
            new_values = []
            for v in values:
                new = "'%s'" % v
                new_values.append(new)
            joined = ','.join(new_values)
            val = "(%s)" % joined
        else:
            op = self.operators[op]
        if 'like' in op or 'ilike' in op:
            val = val.replace('*', '%')
        out = f'{groups_start} {combinator} {col} {op} {val} {groups_end}'
        return out

    def _term_to_sql_order(self, term: OrderTerm) -> str:
        selection = self._gen_sql_col(term)
        direction = term.parsed[0].direction
        return f'order by {selection} {direction}'

    def _term_to_sql_range(self, term: RangeTerm) -> str:
        return f'limit {term.parsed[0].end} offset {term.parsed[0].start}'

    def _term_to_sql_update(self, term: SelectTerm) -> str:
        if not self.data:
            return None
        out = self._gen_sql_update(term)
        return out

    # mapper methods - used by public methods

    def _gen_sql_select_clause(self) -> str:
        out = self.select_map(self._term_to_sql_select)
        if not out:
            sql_select = f'select * from {self.table_name}'
        else:
            joined = ",".join(out)
            sql_select = f"select {self.json_array_sql}({joined}) from {self.table_name}"
        return sql_select

    def _gen_sql_where_clause(self) -> str:
        out = self.where_map(self._term_to_sql_where)
        if not out:
            sql_where = ''
        else:
            joined = ' '.join(out)
            sql_where = f'where {joined}'
        return sql_where

    def _gen_sql_order_clause(self) -> str:
        out = self.order_map(self._term_to_sql_order)
        if not out:
            return ''
        else:
            return out[0]

    def _gen_sql_range_clause(self) -> str:
        out = self.range_map(self._term_to_sql_range)
        if not out:
            return ''
        else:
            return out[0]

    # public methods - called by constructor

    def sql_select(self) -> str:
        _select = self._gen_sql_select_clause()
        _where = self._gen_sql_where_clause()
        _order = self._gen_sql_order_clause()
        _range = self._gen_sql_range_clause()
        return f'{_select} {_where} {_order} {_range}'

    def sql_update(self) -> str:
        out = self.set_map(self._term_to_sql_update)
        if not out:
            return ''
        else:
            _set = out[0]
            _where = self._gen_sql_where_clause()
            return f'update {self.table_name} {_set} {_where}'

    def sql_delete(self) -> str:
        _where = self._gen_sql_where_clause()
        return f'delete from {self.table_name} {_where}'


class SqliteQueryGenerator(SqlGenerator):

    """Generate SQL for SQLite json1 backed tables, from a given UriQuery."""

    db_init_sql = None
    json_array_sql = 'json_array'

    # Helper functions - used by mappers

    def _gen_sql_key_selection(self, term: SelectTerm, parsed: Key) -> str:
        return f"json_extract(data, '$.{term.original}')"

    def _gen_sql_array_selection(self, term: SelectTerm, parsed: ArraySpecific) -> str:
        return f"json_extract(data, '$.{term.original}')"

    def _gen_sql_array_sub_selection(
        self,
        term: SelectTerm,
        parsed: Union[
            ArraySpecificSingle,
            ArraySpecificMultiple,
            ArrayBroadcastSingle,
            ArrayBroadcastMultiple,
        ],
    ) -> str:
        if (
            isinstance(parsed, ArraySpecificSingle)
            or isinstance(parsed, ArraySpecificMultiple)
        ):
            fullkey = f"and fullkey = '$.{term.bare_term}[{parsed.idx}]'"
            vals = 'vals'
        else:
            fullkey = ''
            vals = 'json_group_array(vals)'
        temp = []
        for key in parsed.sub_selections:
            temp.append(f"json_extract(value, '$.{key}')")
        sub_selections = ','.join(temp)
        sub_selections = f'json_array({sub_selections})' if len(temp) > 1 else f'{sub_selections}'
        selection = f"""
                (case when json_extract(data, '$.{term.bare_term}') is not null then (
                    select {vals} from (
                        select
                            {sub_selections} as vals
                        from (
                            select key, value, fullkey, path
                            from {self.table_name}, json_tree({self.table_name}.data)
                            where path = '$.{term.bare_term}'
                            {fullkey}
                            )
                        )
                    )
                else null end)
            """
        return selection

    def _gen_sql_col(self, term: Union[SelectTerm, WhereTerm, OrderTerm]) -> str:
        if isinstance(term, WhereTerm) or isinstance(term, OrderTerm):
            select_term = term.parsed[0].select_term
        elif isinstance(term, SelectTerm):
            select_term = term
        if len(select_term.parsed) > 1:
            test_select_term = select_term.parsed[-1]
            if isinstance(test_select_term, ArraySpecific):
                target = select_term.original
            elif isinstance(test_select_term, ArraySpecificSingle):
                _key = select_term.bare_term
                _idx = select_term.parsed[-1].idx
                _col = select_term.parsed[-1].sub_selections[0]
                target = f'{_key}[{_idx}].{_col}'
            else:
                target = select_term.bare_term
        else:
            if not isinstance(select_term.parsed[0], Key):
                raise Exception(f'Invalid term {term.original}')
            target = select_term.parsed[0].element
        col = f"json_extract(data, '$.{target}')"
        return col

    def _gen_sql_update(self, term: Key) -> str:
        key = term.parsed[0].select_term.bare_term
        assert self.data.get(key) is not None, f'Target key of update: {key} not found in payload'
        assert len(self.data.keys()) == 1, f'Cannot update more than one key per statement'
        new = json.dumps(self.data)
        return f"set data = json_patch(data, '{new}')"


class PostgresQueryGenerator(SqlGenerator):

    json_array_sql = 'jsonb_build_array'
    db_init_sql = [
        """
        create or replace function filter_array_elements(data jsonb, keys text[])
            returns jsonb as $$
            declare key text;
            declare element jsonb;
            declare filtered jsonb;
            declare out jsonb;
            declare val jsonb;
            begin
                create temporary table if not exists info(v jsonb) on commit drop;
                for element in select jsonb_array_elements(data) loop
                    for key in select unnest(keys) loop
                        if filtered is not null then
                            filtered := filtered || jsonb_extract_path(element, key);
                        else
                            filtered := jsonb_extract_path(element, key);
                        end if;
                    if filtered is null then
                        filtered := '[]'::jsonb;
                    end if;
                    end loop;
                insert into info values (filtered);
                filtered := null;
                end loop;
                out := '[]'::jsonb;
                for val in select * from info loop
                    out := out || jsonb_build_array(val);
                end loop;
                return out;
            end;
        $$ language plpgsql;
        """,
        """
        create or replace function unique_data()
        returns trigger as $$
            begin
                NEW.uniq := md5(NEW.data::text);
                return new;
            end;
        $$ language plpgsql;
        """
    ]

    def _gen_select_target(self, term_attr: str) -> str:
        return term_attr.replace('.', ',') if '.' in term_attr else term_attr

    def _gen_sql_key_selection(self, term: SelectTerm, parsed: Key) -> str:
        target = self._gen_select_target(term.original)
        selection = f"data#>'{{{target}}}'"
        return selection

    def _gen_sql_array_selection(self, term: SelectTerm, parsed: ArraySpecific) -> str:
        target = self._gen_select_target(term.bare_term)
        selection = f"""
            case when data#>'{{{target}}}'->{parsed.idx} is not null then
                data#>'{{{target}}}'->{parsed.idx}
            else null end
            """
        return selection

    def _gen_sql_array_sub_selection(
        self,
        term: SelectTerm,
        parsed: Union[
            ArraySpecificSingle,
            ArraySpecificMultiple,
            ArrayBroadcastSingle,
            ArrayBroadcastMultiple,
        ],
    ) -> str:
        target = self._gen_select_target(term.bare_term)
        sub_selections = ','.join(parsed.sub_selections)
        data_selection_expr = f"filter_array_elements(data#>'{{{target}}}','{{{sub_selections}}}')"
        if (
            isinstance(parsed, ArraySpecificSingle)
            or isinstance(parsed, ArraySpecificMultiple)
        ):
            data_selection_expr = f'{data_selection_expr}->{parsed.idx}'
        selection = f"""
            case
                when data#>'{{{target}}}' is not null
                and jsonb_typeof(data#>'{{{target}}}') = 'array'
            then {data_selection_expr}
            else null end
            """
        return selection

    def _gen_sql_col(self, term: Union[SelectTerm, WhereTerm, OrderTerm]) -> str:
        if isinstance(term, WhereTerm) or isinstance(term, OrderTerm):
            select_term = term.parsed[0].select_term
        elif isinstance(term, SelectTerm):
            select_term = term
        if isinstance(term, WhereTerm):
            final_select_op = '#>>' # due to integer comparisons
        else:
            final_select_op = '#>'
        if len(select_term.parsed) > 1:
            test_select_term = select_term.parsed[-1]
            if isinstance(test_select_term, ArraySpecific):
                target = self._gen_select_target(select_term.bare_term)
                _idx = select_term.parsed[-1].idx
                col = f"data#>'{{{target}}}'{final_select_op}'{{{_idx}}}'"
            elif isinstance(test_select_term, ArraySpecificSingle):
                target = self._gen_select_target(select_term.bare_term)
                _idx = select_term.parsed[-1].idx
                _col = select_term.parsed[-1].sub_selections[0]
                col = f"data#>'{{{target}}}'#>'{{{_idx}}}'#>'{{{_col}}}'"
            else:
                target = self._gen_select_target(select_term.bare_term)
                col = f"data{final_select_op}'{{{target}}}'"
        else:
            if not isinstance(select_term.parsed[0], Key):
                raise Exception(f'Invalid term {term.original}')
            target = select_term.parsed[0].element
            col = f"data{final_select_op}'{{{target}}}'"
        if isinstance(term, WhereTerm):
            try:
                integer_ops = ['eq', 'gt', 'gte', 'lt', 'lte', 'neq']
                int(term.parsed[0].val)
                if term.parsed[0].op in integer_ops:
                    col = f'({col})::int'
            except ValueError:
                pass
        return col

    def _gen_sql_update(self, term: Key) -> str:
        key = term.parsed[0].select_term.bare_term
        assert self.data.get(key) is not None, f'Target key of update: {key} not found in payload'
        assert len(self.data.keys()) == 1, f'Cannot update more than one key per statement'
        val = self.data[key]
        return f"set data = jsonb_set(data, '{{{key}}}', '{val}')"
