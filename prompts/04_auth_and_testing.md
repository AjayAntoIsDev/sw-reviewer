Authentication testing prompt:

If a project includes sign up or login:

- Test standard sign up or login flow.
- Test at least one OAuth provider if OAuth is offered.
- Confirm the account can be created by the reviewer without relying on a premade special account.
- Reject if access depends on a special Shipwright account, shared reviewer account, or any premade account provided just for submission review.

Testing standard:

- Use the product like a normal user.
- Verify the core features, not just the landing page.
- If key features depend on auth, complete auth and test those features.
- If the app looks functional but the critical path fails, mark it as not working.
- If only non-critical polish issues exist, that may still be approvable.

What counts as working:

- The primary promised use case can be exercised successfully.
- Required demo links or distribution artifacts are accessible.
- Instructions are sufficient to run, install, or test the project in the intended way.
