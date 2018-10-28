# dice - A maubot plugin that rolls dice.
# Copyright (C) 2018 Tulir Asokan
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
from typing import Match
import operator
import random
import ast
import re

from maubot import Plugin, CommandSpec, Command, Argument, MessageEvent

ARG_PATTERN = "$pattern"
COMMAND_ROLL = f"roll {ARG_PATTERN}"
COMMAND_ROLL_DEFAULT = "roll"

pattern_regex = re.compile("([0-9]{0,2})d([0-9]{1,2})")

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

_OP_LIMITS = {
    ast.Pow: (1000, 1000),
    ast.LShift: (1000, 1000),
    ast.Mult: (1_000_000_000_000_000, 1_000_000_000_000_000),
    ast.Div: (1_000_000_000_000_000, 1_000_000_000_000_000),
    ast.FloorDiv: (1_000_000_000_000_000, 1_000_000_000_000_000),
    ast.Mod: (1_000_000_000_000_000, 1_000_000_000_000_000),
}


# AST-based calculator from https://stackoverflow.com/a/33030616/2120293
class Calc(ast.NodeVisitor):
    def visit_BinOp(self, node):
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
        op(left, right)

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        try:
            op = _OP_MAP[type(node.op)]
        except KeyError:
            raise SyntaxError(f"Operator {type(node.op).__name__} not allowed")
        return op(operand)

    def visit_Num(self, node):
        return node.n

    def visit_Expr(self, node):
        return self.visit(node.value)

    @classmethod
    def evaluate(cls, expression):
        tree = ast.parse(expression)
        return cls().visit(tree.body[0])


class DiceBot(Plugin):
    async def start(self) -> None:
        self.set_command_spec(CommandSpec(
            commands=[Command(
                syntax=COMMAND_ROLL,
                description="Roll dice",
                arguments={
                    ARG_PATTERN: Argument(description="The dice pattern to roll", matches=".+",
                                          required=True),
                },
            ), Command(
                syntax=COMMAND_ROLL_DEFAULT,
                description="Roll a single normal 6-sided dice",
            )],
        ))
        self.client.add_command_handler(COMMAND_ROLL, self.roll)
        self.client.add_command_handler(COMMAND_ROLL_DEFAULT, self.default_roll)

    async def stop(self) -> None:
        self.client.remove_command_handler(COMMAND_ROLL, self.roll)
        self.client.remove_command_handler(COMMAND_ROLL_DEFAULT, self.default_roll)

    @staticmethod
    def randomize(number: int, size: int) -> int:
        if size < 0 or number < 0:
            raise ValueError("randomize() only accepts non-negative values")
        if size == 0 or number == 0:
            return 0
        elif size == 1:
            return number
        result = 0
        for i in range(number):
            result += random.randint(1, size)
        return result

    @classmethod
    def replacer(cls, match: Match) -> str:
        number = int(match.group(1) or "1")
        size = int(match.group(2))
        return str(cls.randomize(number, size))

    async def default_roll(self, evt: MessageEvent) -> None:
        await evt.reply(str(self.randomize(1, 6)))

    async def roll(self, evt: MessageEvent) -> None:
        pattern = evt.content.command.arguments[ARG_PATTERN]
        if len(pattern) > 64:
            await evt.reply("Bad pattern 3:<")
        self.log.debug(f"Handling `{pattern}` from {evt.sender}")
        pattern = pattern_regex.sub(self.replacer, pattern)
        try:
            result = Calc.evaluate(pattern)
            result = str(round(result, 2))
            if len(result) > 512:
                raise ValueError("Result too long")
        except (TypeError, ValueError, SyntaxError, KeyError, OverflowError):
            self.log.debug(f"Failed to evaluate `{pattern}`", exc_info=True)
            await evt.reply("Bad pattern 3:<")
            return
        await evt.reply(result)
