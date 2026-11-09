# How to contribute

Hello! Thanks for considering contributing to **comodo**.

All contributions are welcome, but we have some guidance on how to approach this.

## Reporting bugs / requesting features

If you have found a bug, or would like to raise a request for a new feature,
we ask you to please raise an Issue on our [backlog](https://github.com/comodo-lab/comodo/issues).

If it helps you, there are templates to help guide you through the information we need to asses your submission.

Otherwise, please try to include as much detail as you can about what has gone wrong or what you would like to see changed.

## Contributing fixes / features

To contribute bug fixes or new features to **comodo**, please follow the following process:
1. If it does not exist, raise an Issue on the [backlog](https://github.com/comodo-lab/comodo/issues)
describing the bug / feature and the plan for changes.
2. Make a fork of the **comodo** repo.
3. Comment on the backlog Issue notifying the community of your intention to work
on the issue and how long you expect this might take (this is not a deadline,
but it helps others identify if a planned development has gone stale) and add a
link to the branch on your fork where you are working.
4. Please make sure you add relevant tests for your changes:
   - Add test(s) that would fail without your changes.
   - Add unit test(s) that verify the correct behaviour of your changes in isolation.
   - Add integration test(s) that verify the correct behaviour of your changes at the component level.
   - Make sure all the stack's tests pass after your changes.
See the [Testing](README.md#testing) section of the README for more information on how to run the tests.
5. Also, ensure you lint your contribution using black, so that it is consistent with the rest of the codebase.
6. When the contribution is ready, submit it via a Pull Request **to the _dev_ branch**.
7. The original authors will review your submission and may request that you make changes.

## Docs

Contributions to documentation as well as code are welcome, via the above process.

The general **comodo** documentation is in the [README](README.md) file.
Additionally, each component has its own README file in its directory.

## Asking questions

If you want to ask questions about **comodo** please use the Discussions tab on the repo.

The original authors are also available for individual discussions;
please feel free to reach out directly to them.
