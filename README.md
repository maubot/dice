# dice

A [maubot](https://github.com/maubot/maubot) that rolls dice. Has built-in calculator.

## Usage

The base command is `!roll`.

To roll a dice, pass `XdY` as an argument, where `X` is the number of dice
(optional) and `Y` is the number of sides in each dice. `Y` can be passed as a
specific range as well (for example: `{0,9}`, `{-5,-1}`).

Most Python math and bitwise operators and basic `math` module functions are
also supported, which means you can roll different kinds of dice and combine
the results however you like.
