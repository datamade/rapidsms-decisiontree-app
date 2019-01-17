rapidsms-decisiontree-app
=========================

This application is a generic implementation of a decision tree, which is
completely database-configurable. Users are asked questions and respond via
SMS messages using the RapidSMS framework built on top of Django. 
`Dimagi <http://www.dimagi.com/>`_ wrote the original code for this project, and `Caktus
Consulting Group, LLC <http://www.caktusgroup.com/services>`_ currently packages and maintains it.

Visit `the parent repo <https://github.com/caktus/rapidsms-decisiontree-app>`_ to learn about features, installation, and the test suite. See the `full documentation <http://rapidsms-decisiontree-app.readthedocs.org/>`_ for a complete overview of usage.

DataMade forked and customized ``rapidsms-decisiontree-app`` to meet the requirements of 
`Coordinated Entry Screening (CES) <https://github.com/datamade/coordinated-entry-screening>`_, a tool to help people experiencing homelessness find resources. 

Customizations
------------
This fork includes several adjustments – most notably, significant, CES-specific changes made to the data models and the ``handle`` function in the `the decisiontree App <https://github.com/datamade/rapidsms-decisiontree-app/blob/master/decisiontree/app.py>`_.

The decisiontree App and data models
~~~~~~~~~~~~~~~~~~~~~~

* The CES tool returns either questions or resource recommendations. This fork renames the "Question" model as "Message" and requires a Transition (the way users navigate between survey questions) to have a ``next_state``. See `this pull request <https://github.com/datamade/rapidsms-decisiontree-app/pull/2>`_ for the full conversation about these changes. 

* The CES tool also tracks user analytics, such as, identifying when users cancel a survey (i.e., by selecting "goodbye"). This fork adds a ``state_at_close`` field to `the Session model <https://github.com/datamade/rapidsms-decisiontree-app/pull/18>`_.  

* Later versions of Twilio allow for messages longer than 160 characters! `This fork adjusts for that <https://github.com/datamade/rapidsms-decisiontree-app/pull/23>`_.

Other notable changes
~~~~~~~~~~~~~~~~~~~~~~

* updates the codebase to use `Django 1.11 and Python 3 <https://github.com/datamade/rapidsms-decisiontree-app/pull/1>`_
* adds an `INVALID_ANSWER_RESPONSE settings variable <https://github.com/datamade/rapidsms-decisiontree-app/pull/20>`_

The basic functionality of `the decisiontree App <https://github.com/datamade/rapidsms-decisiontree-app/blob/master/decisiontree/app.py>`_ remains intact. However, these changes are designed to specifically cooperate with the CES tool and the DataMade fork of RapidSMS: they may not integrate easily with other implementations of ``rapidsms-decisiontree-app``. 