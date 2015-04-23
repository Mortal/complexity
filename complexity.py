import ast
import sys
import argparse
import collections

import sympy

from sympy import Basic
from sympy.printing.str import StrPrinter


class CustomStrPrinter(StrPrinter):
    def _print_Dummy(self, expr):
        return expr.name


Basic.__str__ = lambda self: CustomStrPrinter().doprint(self)


def Dummy(name):
    return sympy.Dummy(name, integer=True, nonnegative=True)


class VisitorBase(ast.NodeVisitor):
    def __init__(self, source):
        self._source_lines = source.split('\n')
        self.scope_stack = []
        self.current_scope = None
        self.unhandled = set()
        self.log_lines = collections.defaultdict(list)
        self.current_line = [None]

    def push_scope(self, s):
        self.scope_stack.append(self.current_scope)
        self.current_scope = s

    def pop_scope(self):
        self.current_scope = self.scope_stack.pop()

    def visit(self, node):
        if isinstance(node, list):
            for x in node:
                self.visit(x)
            return
        try:
            current_line = node.lineno - 1
        except AttributeError:
            current_line = None
        self.current_line.append(current_line)
        try:
            return super(VisitorBase, self).visit(node)
        except:
            self.source_backtrace(node, sys.stderr)
            raise
        finally:
            self.current_line.pop()

    def log(self, s):
        self.log_lines[self.current_line[-1]].append(s)

    def source_backtrace(self, node, file):
        try:
            lineno = node.lineno
            col_offset = node.col_offset
        except AttributeError:
            lineno = col_offset = None
        print('At node %s' % node, file=file)
        if lineno is not None and lineno > 0:
            print(self._source_lines[lineno - 1], file=file)
            print(' ' * col_offset + '^', file=file)

    def generic_visit(self, node):
        if type(node) not in self.unhandled:
            self.source_backtrace(node, sys.stderr)
            print("%s unhandled" % (type(node).__name__,), file=sys.stderr)
        self.unhandled.add(type(node).__name__)

    def visit_children(self, node):
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def visit_Module(self, node):
        self.visit_children(node)

    def print_line(self, i):
        line = self._source_lines[i]
        if i not in self.log_lines:
            print(line)
            return
        length = max(len(line), 38)
        for j, c in enumerate(self.log_lines[i]):
            if j == 0:
                l = line
            else:
                l = ''
            print('%s# %s' % (l.ljust(length), c))
        del self.log_lines[i]


class Scope(object):
    def __init__(self, parent, parameters):
        self._parent = parent
        self._locals = {
            n: Dummy(n)
            for n in parameters
        }
        self.steps = Dummy('steps')
        self._effects = {}
        self._output = None
        self.add_effect(self.steps, sympy.S.Zero)
        self.add_one_step()

    def add_one_step(self):
        s = self
        while s is not None:
            self.add_effect(s.steps, s.steps + 1)
            s = s._parent

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, x):
        if self._output is None:
            self._output = x
        else:
            raise AttributeError("Output is already set")

    @property
    def changed_vars(self):
        return set(self[v] for v in self._effects.keys())

    def affect(self, expr):
        sub = {
            self[n]: e
            for n, e in self._effects.items()
        }
        return expr.subs(sub)

    def __getitem__(self, name):
        if isinstance(name, ast.AST):
            raise TypeError("Try to lookup a %s" % (name,))
        elif isinstance(name, sympy.Symbol):
            return name
        try:
            return self._locals[name]
        except KeyError:
            if self._parent is None:
                raise KeyError(name)
            return self._parent[name]

    def add_effect(self, name, expr):
        if isinstance(name, ast.AST):
            raise TypeError("Try to add_effect on a %s" % (name,))
        if expr is None:
            raise TypeError("Try to add_effect with None")
        if isinstance(name, str):
            try:
                name = self[name]
            except KeyError:
                self._locals[name] = Dummy(name)
                name = self._locals[name]
        self._effects[name] = self.affect(expr)


def repeated(n, i, e, a, b):
    # let n_a = n; n_{a+k+1} = e(n=n_{a+k}, i=a+k+1)
    # return n_b
    if e.has(i):
        if e.has(n):
            if not (e - n).has(n):
                term = e - n
                return n + sympy.summation(term, (i, a, b))
            raise NotImplementedError("has i and n")
        else:
            return e.subs(i, b)
    else:
        if e.has(n):
            if not (e - n).has(n):
                term = e - n
                return n + term * (b - a + 1)
            c, args = e.as_coeff_add(n)
            arg, = args
            if not (arg / n).simplify().has(n):
                coeff = arg / n
                # print("Coefficient is %s, iterations is %s" %
                #       (coeff, (b-a+1)))
                return n * coeff ** (b - a + 1)
            raise NotImplementedError
        else:
            return e


def termination_function(e):
    if isinstance(e, (sympy.LessThan, sympy.GreaterThan)):
        c = 0
    elif isinstance(e, (sympy.StrictLessThan, sympy.StrictGreaterThan)):
        c = 1
    else:
        raise NotImplementedError(str(type(e)))
    return e.gts - e.lts - c


class Visitor(VisitorBase):
    def visit_Module(self, node):
        linenos = [v.lineno - 1 for v in node.body]
        linenos[0] = 0
        linenos.append(len(self._source_lines))
        for v, i, j in zip(node.body, linenos[:-1], linenos[1:]):
            self.visit(v)
            for k in range(i, j):
                self.print_line(k)

    def visit_FunctionDef(self, node):
        # print((' Function %s (line %s) ' % (node.name, node.lineno))
        #       .center(79, '='))
        self.push_scope(Scope(self.current_scope, [arg.arg for arg in node.args.args]))
        self.visit(node.body)
        def BigO(e):
            return sympy.Order(e, (self.current_scope[node.args.args[0].arg], sympy.oo))
        self.log("Function %s: O(%s)" %
                 (node.name,
                  BigO(self.current_scope.affect(self.current_scope.steps),).args[0]))
        if self.current_scope.output is not None:
            print("Result: %s" % (self.current_scope.affect(self.current_scope.output),))
        # for n, e in self.current_scope._effects.items():
        #     ee = BigO(e)
        #     if ee.args:
        #         print("%s:\n%s = O(%s)" % (n, e, ee.args[0]))
        #     else:
        #         print("%s:\n%s = O(??)" % (n, e))
        self.pop_scope()
        if self.unhandled:
            print("Unhandled types: %s" %
                  ', '.join(str(c) for c in self.unhandled))
            self.unhandled = type(self.unhandled)()
        print('')

    def visit_Return(self, node):
        self.log("Result: %s" % (self.current_scope.affect(self.visit(node.value)),))

    def visit_Assign(self, node):
        target, = node.targets
        name = target.id
        expr = self.visit(node.value)
        self.current_scope.add_effect(name, expr)
        self.log("%s = %s" % (name, expr))

    def visit_BinOp(self, node):
        return self.binop(self.visit(node.left), node.op, self.visit(node.right))

    def visit_Compare(self, node):
        left = self.visit(node.left)
        rights = [self.visit(c) for c in node.comparators]
        lefts = [left] + rights[:-1]
        res = None
        for left, op, right in zip(lefts, node.ops, rights):
            r = self.binop(left, op, right)
            if res is None:
                res = r
            else:
                res = self.binop(res, ast.And, r)
        return res

    def binop(self, left, op, right):
        if isinstance(op, ast.AST):
            op = type(op)
        if op == ast.Add:
            return left + right
        elif op == ast.Sub:
            return left - right
        elif op == ast.Mult:
            return left * right
        elif op == ast.Div:
            return left / right
        elif op == ast.And:
            return sympy.And(left, right)
        elif op == ast.Lt:
            return sympy.StrictLessThan(left, right)
        elif op == ast.LtE:
            return sympy.LessThan(left, right)
        elif op == ast.Gt:
            return sympy.StrictGreaterThan(left, right)
        elif op == ast.GtE:
            return sympy.GreaterThan(left, right)
        else:
            raise TypeError("Unknown op %s" % (op,))

    def visit_AugAssign(self, node):
        target = node.target
        name = target.id
        expr = self.visit(node.value)
        aug_expr = self.binop(self.current_scope[name], node.op, expr)
        self.current_scope.add_effect(name, aug_expr)
        self.log("%s = %s" % (name, aug_expr))

    def visit_Num(self, node):
        return sympy.Rational(node.n)

    def visit_Name(self, node):
        return self.current_scope[node.id]

    def visit_For(self, node):
        assert isinstance(node.iter, ast.Call)
        if node.iter.func.id == 'range':
            args = node.iter.args
            if len(args) == 1:
                a = 0
                b = self.visit(args[0])
            elif len(args) == 2:
                a, b = self.visit(args[0]), self.visit(args[1])
            else:
                raise ValueError("Cannot handle 3-arg range")
            sc = self.current_scope
            self.push_scope(Scope(self.current_scope, [node.target.id]))
            itervar = self.current_scope[node.target.id]
            # print("FOR")
            self.visit(node.body)
            # print("ENDFOR")
            its = None
            for n, e in self.current_scope._effects.items():
                nsymb = self.current_scope[n]
                ee = repeated(nsymb, itervar, e, a, b - 1)
                if n == sc.steps:
                    its = ee - sc.steps
                sc.add_effect(n, ee)
                # if e.has(nsymb):
                #     ee = repeated(nsymb, itervar, e, a, b - 1)
                #     sc.add_effect(n, ee)
                # elif e.has(itervar):
                #     sc.add_effect(n, e.subs(itervar, b - 1))
                # else:
                #     sc.add_effect(n, e)
            self.pop_scope()
            self.log("%s iterations" % (its,))
        else:
            raise ValueError("Cannot handle non-range for")

    def visit_While(self, node):
        test = self.visit(node.test)
        test_vars = test.free_symbols
        sc = self.current_scope
        self.push_scope(Scope(self.current_scope, []))
        # print("WHILE")
        self.visit(node.body)
        # print("ENDWHILE")
        it_vars = test_vars & self.current_scope.changed_vars
        if not it_vars:
            raise ValueError("No iteration variables were changed: %s %s" %
                             (test_vars, self.current_scope.changed_vars))
        effects = {}
        itervar = Dummy('itervar')
        imax = Dummy('imax')
        for n, e in self.current_scope._effects.items():
            nsymb = self.current_scope[n]
            effects[nsymb] = sc.affect(repeated(nsymb, itervar, e, 1, imax))
        o = termination_function(test).subs(effects)
        iterations = sympy.solve(o, imax, dict=True)[0][imax]
        # self.log("Solve %s for %s => %s" % (o, imax, iterations))
        # iterations = iterations * 2
        # self.log(iterations.simplify())
        s = self.current_scope
        self.pop_scope()
        its = None
        for n, e in effects.items():
            ee = e.subs(imax, iterations)
            if n == self.current_scope.steps:
                its = ee
            self.current_scope.add_effect(n, ee)
        self.log("%s iterations" % (its,))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()
    with open(args.filename) as fp:
        source = fp.read()
    o = ast.parse(source, args.filename, 'exec')
    visitor = Visitor(source)
    visitor.visit(o)


if __name__ == "__main__":
    main()
