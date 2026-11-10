> **V<N> accepted — implementation can start**
>
> 1. Review [<Ready work order>](<versioned-wiki-work-order-path>).
> 2. Confirm its repository paths are authorized.
> 3. Run `/ob-implement work-order:<id>`.
> 4. Review and merge the linked implementation PRs, deploy, and return to the
>    [work-order queue](<versioned-wiki-queue-path>) for the next Ready order.
> 5. Generate and review Terraform independently; a human applies it.
> 6. Run `/ob-verify` after deployment and apply.
