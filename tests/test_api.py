# -*- coding: utf-8 -*-

from learn_snowflake import api


def test():
    _ = api


if __name__ == "__main__":
    from learn_snowflake.tests import run_cov_test

    run_cov_test(
        __file__,
        "learn_snowflake.api",
        preview=False,
    )
