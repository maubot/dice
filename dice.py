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
    ast.FloorDiv: operator.floordiv,
    ast.Invert: operator.neg,
    ast.USub: operator.neg,
}


# AST-based calculator from https://stackoverflow.com/a/33030616/2120293
class Calc(ast.NodeVisitor):
    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        return _OP_MAP[type(node.op)](left, right)

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        return _OP_MAP[type(node.op)](operand)

    def visit_Num(self, node):
        return node.n

    def visit_Expr(self, node):
        return self.visit(node.value)

    @classmethod
    def evaluate(cls, expression):
        tree = ast.parse(expression)
        calc = cls()
        return calc.visit(tree.body[0])


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
        self.log.debug(f"Handling `{pattern}` from {evt.sender}")
        pattern = pattern_regex.sub(self.replacer, pattern)
        try:
            result = Calc.evaluate(pattern)
            await evt.reply(str(round(result, 2)))
        except (TypeError, SyntaxError):
            self.log.exception(f"Failed to evaluate `{pattern}`")
            await evt.reply("Bad pattern 3:<")
            return
