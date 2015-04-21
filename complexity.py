import ast
import sys
import argparse


class VisitorBase(ast.NodeVisitor):
    def __init__(self, source):
        self._source_lines = source.split('\n')

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
        print(r'%% a %s' % (type(node).__name__,))


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
