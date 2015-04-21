import ast
import sys
import argparse

import sympy


class VisitorBase(ast.NodeVisitor):
    def __init__(self, source):
        self._source_lines = source.split('\n')
        self.scope_stack = []
        self.current_scope = None
        self.unhandled = set()

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
            return super(VisitorBase, self).visit(node)
        except:
            self.source_backtrace(node, sys.stderr)
            raise

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


class Scope(object):
    def __init__(self, parent, parameters):
        self._parent = parent
        self._locals = {
            n: sympy.Dummy(n)
            for n in parameters
        }
        self._effects = {}
        self._output = None

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, x):
        if self._output is None:
            self._output = x
        else:
            raise AttributeError("Output is already set")

    def __getitem__(self, name):
        if isinstance(name, ast.AST):
            raise TypeError("Try to lookup a %s" % (name,))
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
        try:
            self[name]
        except KeyError:
            self._locals[name] = sympy.Dummy(name)
        sub = {
            self[n]: e
            for n, e in self._effects.items()
        }
        self._effects[name] = expr.subs(sub)


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
            raise NotImplementedError("has i but not n")
    else:
        if e.has(n):
            if not (e - n).has(n):
                term = e - n
                return n + term * (b - a + 1)
            c, args = e.as_coeff_add(n)
            arg, = args
            if not (arg / n).simplify().has(n):
                coeff = arg / n
                return n + coeff ** (b - a + 1) * n
            raise NotImplementedError
        else:
            return (b - a + 1) * e


class Visitor(VisitorBase):
    def visit_FunctionDef(self, node):
        self.push_scope(Scope(self.current_scope, [arg.arg for arg in node.args.args]))
        self.visit(node.body)
        print("Function %s:" % (node.name,))
        def BigO(e):
            return sympy.Order(e, (self.current_scope[node.args.args[0].arg], sympy.oo))
        if self.current_scope.output is not None:
            print("Result:\n%s" % (self.current_scope.output,))
        for n, e in self.current_scope._effects.items():
            print("%s:\n%s = O(%s)" % (n, e, BigO(e).args[0]))
        self.pop_scope()
        if self.unhandled:
            print("Unhandled types: %s" %
                  ', '.join(str(c) for c in self.unhandled))
            self.unhandled = type(self.unhandled)()
        print('')

    def visit_Return(self, node):
        self.current_scope.output = self.visit(node.value)

    def visit_Assign(self, node):
        target, = node.targets
        name = target.id
        expr = self.visit(node.value)
        self.current_scope.add_effect(name, expr)

    def visit_BinOp(self, node):
        return self.binop(self.visit(node.left), node.op, self.visit(node.right))

    def binop(self, left, op, right):
        if isinstance(op, ast.AST):
            op = type(op)
        if op == ast.Add:
            return left + right
        elif op == ast.Mult:
            return left * right
        else:
            raise TypeError("Unknown op %s" % (op,))

    def visit_AugAssign(self, node):
        target = node.target
        name = target.id
        expr = self.visit(node.value)
        aug_expr = self.binop(self.current_scope[name], node.op, expr)
        self.current_scope.add_effect(name, aug_expr)

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
            self.visit(node.body)
            for n, e in self.current_scope._effects.items():
                nsymb = self.current_scope[n]
                if e.has(nsymb):
                    ee = repeated(nsymb, itervar, e, a, b - 1)
                    sc.add_effect(n, ee)
                elif e.has(itervar):
                    sc.add_effect(n, e.subs(itervar, b - 1))
                else:
                    sc.add_effect(n, e)
            self.pop_scope()
        else:
            raise ValueError("Cannot handle non-range for")


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
