# dice
A [maubot](https://github.com/maubot/maubot) that rolls dice. Has built-in calculator.

## Usage
The base command is `!roll`. To roll dice, pass `XdY` as an argument, where `X`
is the number of dice (optional) and `Y` is the number of sides in each dice.
Additionally, you can use `XwodY` to roll a pool of `X` ten sided dice and 
compare them against the threshold of `Y` and subtracting all natural ones from 
the result.
Most Python math and bitwise operators and basic `math` module functions are
also supported, which means you can roll different kinds of dice and combine
the results however you like.
