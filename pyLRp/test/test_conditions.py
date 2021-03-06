
import unittest
import sys
import logging

from . import utils
from ..lexer import InclusiveInitialCondition, ExclusiveInitialCondition

class DefaultConditionsTestCase(utils.FailOnLogTestCase,
                                utils.ParseResultTestCase):

    def test_sof(self):
        parser, _ = self.compile(r"""
# epl (expressive parrot language)
%lexer

\s+ %restart

# allow shebang
<$SOF>\#!.* %restart

# otherwise the language has "" comments
"[^"]*" %restart

# and parrots
[Tt]his THIS
parrot PARROT
is IS
dead DEAD
\#! FAKE

%parser

doc:
    %empty: $$.sem = []
    doc THIS PARROT IS DEAD "!": $$.sem = $1.sem + ['parrot']
    doc FAKE: $$.sem = $1.sem + ['fake']
""")

        # correct shebang
        self.verify_parse_result(parser, br"""#! shebang comment
This "ljljlkj" parrot is dead!
""", ["parrot"])

        # no shebang <$SOF> must be inclusive
        self.verify_parse_result(parser, br"""This parrot is dead!""", ["parrot"])

        # the FAKE shebang must be parsed correctly in other contexts
        self.verify_parse_result(parser, br""" #! This parrot is dead ! #!""",
                                 ["fake", "parrot", "fake"])

        # several incorrect versions
        self.verify_syntax_error(parser, br"""This#! parrot is dead!""")
        self.verify_syntax_error(parser, br"""#! parrot is dead!
#! welcome to the ministry of silly walks""")
        self.verify_syntax_error(parser, br"""
#! shebang comment
This parrot is dead!
""")
        self.verify_syntax_error(parser, br""" #! shebang comment
This "ljljlkj" parrot is dead!
""")
        self.verify_syntax_error(parser, br"""##! shebang comment
This "ljljlkj" parrot is dead!
""")

    def test_sol(self):
        parser, _ = self.compile(r"""
# yapl (yet another parrot language)
%lexer

\s+ %restart

# here for confusion and to verify longest-match sematics
<$SOF>--c %restart

# this language has start of file --| |-- block comments
<$SOF>--\|([^|]*|\|[^\-]|\|-[^\-])*\|-- %restart

# this language has start of line -- comments
^--.* %restart

# and parrots
[Tt]his THIS
parrot PARROT
is IS
dead DEAD

%parser

doc:
    %empty
    doc THIS PARROT IS DEAD "!"
""")

        self.verify_parse_result(parser, br"--comment", None)
        self.verify_syntax_error(parser, br" --comment")
        self.verify_parse_result(parser, br"""This
--
parrot
--
is
--
dead
-- !
!
""", None)
        self.verify_syntax_error(parser, br"""This
--
parrot
--
is --
dead
-- !
!
""")

        # test sol-sof interaction and longest match semantics for
        # %restart
        self.verify_parse_result(parser, br"""--|
  invalid but inside a comment
|--

This parrot is dead!""", None)

class UserDefinedConditionsTest(utils.FailOnLogTestCase,
                                utils.ParseResultTestCase):

    def test_exclincl(self):
        parser, _ = self.compile(r"""
%lexer

%x COMMENT
%s QUOTE

\s+ %restart

# the QUOTSYMB is earlier in the file therefore
# takes precedence, when QUOTE is active
\{ %begin(QUOTE), %restart
<QUOTE>[a-zA-Z_][a-zA-Z0-9_]+ QUOTSYMB
<QUOTE>\} %begin($INITIAL), %restart

[a-zA-Z_][a-zA-Z0-9_]+ SYMB

# comment minilanguage at the courtesy of the flex manual
/\* %push(COMMENT), %restart
<COMMENT>[^*]* %restart
<COMMENT>\*+[^*/]* %restart
<COMMENT>\*+\/ %pop(), %restart

%parser
doc:
    %empty: $$.sem = []
    doc SYMB: $$.sem = $1.sem + ["symb"]
    doc QUOTSYMB: $$.sem = $1.sem + ["quot"]

""")

        self.verify_parse_result(parser, b"/* no comment */", [])
        self.verify_parse_result(parser, b"""
{
    /* no comment */
    quoted
}
/* { */
   notquoted
/* } */
""", ["quot", "symb"])


class ConditionAlgebraTest(unittest.TestCase):

    def test_match(self):
        cond1 = InclusiveInitialCondition("cond1", 0)
        cond2 = InclusiveInitialCondition("cond2", 1, cond1)
        cond3 = ExclusiveInitialCondition("cond3", 2)

        self.assertTrue(cond1.match([cond1]))
        self.assertTrue(cond1.match([cond1, cond3]))
        self.assertTrue(cond2.match([cond2]))
        self.assertTrue(cond3.match([cond3]))
        self.assertTrue(cond3.match([cond1, cond3]))
        self.assertTrue(cond2.match([cond1]))
        self.assertFalse(cond1.match([cond2, cond3]))
        self.assertFalse(cond3.match([cond1, cond2]))
        self.assertFalse(cond2.match([cond3]))
