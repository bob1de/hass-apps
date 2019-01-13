Welcome to the documentation of hass-apps!
==========================================

This is a collection of useful apps to empower Home Assistant even more.

The apps are built on top of the AppDaemon framework. Each has its own,
detailled documentation and includes a sample configuration. Read the
:doc:`getting-started` chapter and start empowering your smart home.


.. rubric:: Active and stable apps:

* :doc:`apps/schedy/index` - The most powerful scheduler for everything
  from lighting to heating


.. rubric:: Deprecated apps that will be removed:

* :doc:`apps/heaty/index` - A scheduler for your heating setup


.. toctree::
   :glob:
   :hidden:
   :maxdepth: 1

   Introduction <self>
   getting-started
   upgrading
   apps/*/index
   CHANGELOG
   CODE_OF_CONDUCT


Donations
---------

.. note::

   I work on this project in my spare time, as many free software
   developers do. And of course, I enjoy this work a lot. There is no
   and will never be a need to pay anything for using this software.

However, if you want to honor the hundreds of hours continuously spent
with writing code and documentation, testing and providing support by
donating me a cup of coffee, a beer in the evening, my monthly hosting
fees or anything else embellishing my day a little more, that would be
awesome. If you decide doing so, I want to thank you very much! Please
be assured that I'm not presuming anybody to donate, it's entirely
your choice.

|paypal-recurring| Ensure ongoing development and support with a monthly
donation, no matter how small.

.. |paypal-recurring| image:: https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif
   :target: https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=PZPNNAJ93TVTQ&source=url

|paypal-once| Or make an one-time donation.

.. |paypal-once| image:: https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif
   :target: https://www.paypal.me/RSchindler

| ETH: 0xa424975a19903F7A6253bA00D5C3F28fACff3C6B
| ZEC: t1RKFyt4qqtqdYfprf8HZoDHRNLNzhe35ED


Getting Help
------------

.. note::

   **If you run into any issue, first consult the documentation
   thoroughly.**
  
   A notable amount of work has gone into it and most aspects should be
   covered already. When this didn't help you're welcome to e.g. ask in
   the `Home Assistant Community <https://community.home-assistant.io/>`_.

When encountering something that seems to be a bug, please open an
`issue on GitHub <https://github.com/efficiosoft/hass-apps/issues>`_ and
attach complete logs with ``debug: true`` set in the app's configuration
illustrating the issue. You won't receive help otherwise.


Contributing
------------

You are welcome to contribute your own apps for AppDaemon to this
project. But please don't submit a pull request without talking to
me first. This is because there is currently no developer documentation
on how to integrate properly with the environment provided by hass-apps
and I want to save you the hassle of re-designing your app after it's
already written.

If you've got an interesting idea for a new app you'd like to contribute,
just open an issue on GitHub and we can discuss it there.

All contributions are subject to the :doc:`CODE_OF_CONDUCT`. Don't
contribute if you don't agree with that.
