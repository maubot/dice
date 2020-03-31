# dice - A maubot plugin that rolls dice.
# Copyright (C) 2019 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import Match, Union, Any, Type
import operator
import random
import math
import ast
import re

from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command

pattern_regex = re.compile("([0-9]{0,9})[dD]([0-9]{1,9})")

_OP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Invert: operator.inv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.RShift: operator.rshift,
    ast.LShift: operator.lshift,
}

_NUM_MAX = 1_000_000_000_000_000
_NUM_MIN = -_NUM_MAX

_OP_LIMITS = {
    ast.Pow: (1000, 1000),
    ast.LShift: (1000, 1000),
    ast.Mult: (1_000_000_000_000_000, 1_000_000_000_000_000),
    ast.Div: (1_000_000_000_000_000, 1_000_000_000_000_000),
    ast.FloorDiv: (1_000_000_000_000_000, 1_000_000_000_000_000),
    ast.Mod: (1_000_000_000_000_000, 1_000_000_000_000_000),
}

_ALLOWED_FUNCS = ["ceil", "copysign", "fabs", "factorial", "gcd", "remainder", "trunc",
                  "exp", "log", "log1p", "log2", "log10", "sqrt",
                  "acos", "asin", "atan", "atan2", "cos", "hypot", "sin", "tan",
                  "degrees", "radians",
                  "acosh", "asinh", "atanh", "cosh", "sinh", "tanh",
                  "erf", "erfc", "gamma", "lgamma"]

_FUNC_MAP = {
    **{func: getattr(math, func) for func in _ALLOWED_FUNCS if hasattr(math, func)},
    "round": round,
    "hash": hash,
    "max": max,
    "min": min,
    "float": float,
    "int": int,
}

_FUNC_LIMITS = {
    "factorial": 1000,
    "exp": 709,
    "sqrt": 1_000_000_000_000_000,
}

_ARG_COUNT_LIMIT = 5


# AST-based calculator from https://stackoverflow.com/a/33030616/2120293
class Calc(ast.NodeVisitor):
    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        try:
            left_max, right_max = _OP_LIMITS[op_type]
            if left > left_max or right > right_max:
                raise ValueError(f"Value over bounds in operator {op_type.__name__}")
        except KeyError:
            pass
        try:
            op = _OP_MAP[op_type]
        except KeyError:
            raise SyntaxError(f"Operator {op_type.__name__} not allowed")
        return op(left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        try:
            op = _OP_MAP[type(node.op)]
        except KeyError:
            raise SyntaxError(f"Operator {type(node.op).__name__} not allowed")
        return op(operand)

    def visit_Num(self, node: ast.Num) -> Any:
        if node.n > _NUM_MAX or node.n < _NUM_MIN:
            raise ValueError(f"Number out of bounds")
        return node.n

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id == "pi":
            return math.pi
        elif node.id == "tau":
            return math.tau
        elif node.id == "e":
            return math.e

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name):
            try:
                func = _FUNC_MAP[node.func.id]
            except KeyError:
                raise NameError(f"Function {node.func.id} is not defined")
            args = [self.visit(arg) for arg in node.args]
            kwargs = {kwarg.arg: self.visit(kwarg.value) for kwarg in node.keywords}
            if len(args) + len(kwargs) > _ARG_COUNT_LIMIT:
                raise ValueError("Too many arguments")
            try:
                limit = _FUNC_LIMITS[node.func.id]
                for value in args:
                    if value > limit:
                        raise ValueError(f"Value over bounds for function {node.func.id}")
                for value in kwargs.values():
                    if value > limit:
                        raise ValueError(f"Value over bounds for function {node.func.id}")
            except KeyError:
                pass
            return func(*args, **kwargs)
        raise SyntaxError("Indirect call")

    def visit_Expr(self, node: ast.Expr) -> Any:
        return self.visit(node.value)

    @classmethod
    def evaluate(cls, expression: str) -> Union[int, float]:
        tree = ast.parse(expression)
        return cls().visit(tree.body[0])


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("show_individual_results")


class DiceBot(Plugin):
    async def start(self) -> None:
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> Type[Config]:
        return Config

    @staticmethod
    def randomize(number: int, size: int) -> int:
        if size < 0 or number < 0:
            raise ValueError("randomize() only accepts non-negative values")
        if size == 0 or number == 0:
            return 0
        elif size == 1:
            return number
        result = 0
        if number < 100:
            for i in range(number):
                result += random.randint(1, size)
        else:
            mean = number * (size + 1) / 2
            variance = number * (size ** 2 - 1) / 12
            while result < number or result > number * size:
                result = int(random.gauss(mean, math.sqrt(variance)))
        return result

    @classmethod
    def replacer(cls, match: Match) -> str:
        number = int(match.group(1) or "1")
        size = int(match.group(2))
        return str(cls.randomize(number, size))

    @command.new("roll")
    @command.argument("pattern", pass_raw=True, required=False)
    async def roll(self, evt: MessageEvent, pattern: str) -> None:
        if not pattern:
            await evt.reply(str(self.randomize(1, 6)))
            return
        elif len(pattern) > 64:
            await evt.reply("Bad pattern 3:<")
            return
        self.log.debug(f"Handling `{pattern}` from {evt.sender}")
        pattern = pattern_regex.sub(self.replacer, pattern)
        try:
            result = Calc.evaluate(pattern)
            result = str(round(result, 2))
            if len(result) > 512:
                raise ValueError("Result too long")
        except (TypeError, NameError, ValueError, SyntaxError, KeyError, OverflowError,
                ZeroDivisionError):
            self.log.debug(f"Failed to evaluate `{pattern}`", exc_info=True)
            await evt.reply("Bad pattern 3:<")
            return
        if self.config["show_individual_results"] and pattern != result:
            result = f"{pattern} = {result}"
        await evt.reply(result)
