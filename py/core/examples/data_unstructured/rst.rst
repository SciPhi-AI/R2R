Header 1
========
--------
Subtitle
--------

Example text.

.. contents:: Table of Contents

Header 2
--------

1. Blah blah ``code`` blah

2. More ``code``, hooray

3. Somé UTF-8°

The UTF-8 quote character in this table used to cause python to go boom. Now docutils just silently ignores it.

.. csv-table:: Things that are Awesome (on a scale of 1-11)
	:quote: ”

	Thing,Awesomeness
	Icecream, 7
	Honey Badgers, 10.5
	Nickelback, -2
	Iron Man, 10
	Iron Man 2, 3
	Tabular Data, 5
	Made up ratings, 11

.. code::

	A block of code

.. code:: python

	python.code('hooray')

.. code:: javascript

	export function ƒ(ɑ, β) {}

.. doctest:: ignored

	>>> some_function()
	'result'

>>> some_function()
'result'

==============  ==========================================================
Travis          http://travis-ci.org/tony/pullv
Docs            http://pullv.rtfd.org
API             http://pullv.readthedocs.org/en/latest/api.html
Issues          https://github.com/tony/pullv/issues
Source          https://github.com/tony/pullv
==============  ==========================================================


.. image:: https://scan.coverity.com/projects/621/badge.svg
	:target: https://scan.coverity.com/projects/621
	:alt: Coverity Scan Build Status

.. image:: https://scan.coverity.com/projects/621/badge.svg
	:alt: Coverity Scan Build Status

Field list
----------

:123456789 123456789 123456789 123456789 123456789 1: Uh-oh! This name is too long!
:123456789 123456789 123456789 123456789 1234567890: this is a long name,
	but no problem!
:123456789 12345: this is not so long, but long enough for the default!
:123456789 1234: this should work even with the default :)

someone@somewhere.org

Press :kbd:`Ctrl+C` to quit


.. raw:: html

    <p><strong>RAW HTML!</strong></p><style> p {color:blue;} </style>
