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
        try:
            return super(VisitorBase, self).visit(node)
        except:
            try:
                lineno = node.lineno
                col_offset = node.col_offset
            except AttributeError:
                lineno = col_offset = None
            print('At node %s' % node, file=sys.stderr)
            if lineno is not None and lineno > 0:
                print(self._source_lines[lineno - 1], file=sys.stderr)
                print(' ' * col_offset + '^', file=sys.stderr)
            raise

    def generic_visit(self, node):
        self.unhandled.add(type(node))

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
        if name in self._effects:
            expr = expr.subs(self[name], self._effects[name])
        self._effects[name] = expr


class Visitor(VisitorBase):
    def visit_FunctionDef(self, node):
        self.push_scope(Scope(self.current_scope, [arg.arg for arg in node.args.args]))
        self.visit_children(node)
        for n, e in self.current_scope._effects.items():
            print("%s:\n%s" % (n, e))
        self.pop_scope()
        if self.unhandled:
            print("Unhandled types: %s" %
                  ', '.join(str(c) for c in self.unhandled))
            self.unhandled = type(self.unhandled)()

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
            self.visit_children(node)
            for n, e in self.current_scope._effects.items():
                nsymb = self.current_scope[n]
                if not e.has(nsymb) and not e.has(itervar):
                    sc.add_effect(n, e)
                    continue
                cterm, iterms = e.as_coeff_add(nsymb)
                if not iterms:
                    sc.add_effect(n, cterm.subs(itervar, b - 1))
                    continue
                iterm, = iterms
                coeff, exponent = iterm.as_coeff_exponent(nsymb)
                if not exponent.is_Number:
                    raise ValueError("Exponent %s is has free symbols" % (exponent,))
                if not coeff.is_Number:
                    raise ValueError("Coefficient %s is has free symbols" % (coeff,))
                if exponent == 1:
                    if coeff == 1:
                        ee = nsymb + sympy.summation(cterm, (itervar, a, b - 1))
                        sc.add_effect(n, ee)
                    elif 0 < coeff < 1:
                        # In the loop, we set x = a + b x, where 0 < b < 1
                        raise ValueError("Recurrence involving %s%s" % (coeff, n))
                    elif coeff > 1:
                        # In the loop, we set x = a + b x, where 0 < b < 1
                        lims = [(s, sympy.oo) for s in 
                        ee = sympy.Order(
                        sc.add_effect(
                        raise ValueError("Recurrence involving %s%s" % (coeff, n))
                    elif coeff < 0:
                        raise ValueError("Recurrence involving %s%s" % (coeff, n))
                elif exponent > 1:
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
