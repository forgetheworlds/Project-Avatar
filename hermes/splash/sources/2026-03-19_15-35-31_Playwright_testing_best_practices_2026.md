In 2026, Playwright best practices emphasize **test isolation**, **network predictability**, and **CI efficiency**. 

1. Docker Isolated Container & User Data Failure `[13][14][15]`

For 2026, the standard is to run tests in a **clean, reproducible Linux environment**. To simulate user data failures (e.g., database timeouts or data corruption) within a container, use **Playwright's Network API** to intercept and modify backend responses.  typescript

```
// Simulate a 500 error for a specific user data fetch in Docker test('handles user data fetch failure', async ({ page }) => { await page.route('**/api/user/profile', route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'Internal Server Error' })
    })
  );
  await page.goto('/profile');
  await expect(page.getByText('Failed to load profile')).toBeVisible();
});

```

Use code with caution.

Copied to clipboard

2. Stripe Test Mode: Success, Decline, & 3D Secure `[10][11][12]`

Use official Stripe test credentials to verify E2E payment flows. 

| Scenario `[7][8][9]` | Card Number | CVC | Result |
| --- | --- | --- | --- |
| **Success** | `4242 4242 4242 4242` | Any | Succeeds with any future expiry. |
| **Generic Decline** | `4000 0000 0000 0002` | Any | Returns `card_declined`. |
| **3D Secure (3DS)** | `4000 0000 0000 3063` | Any | Triggers 3DS authentication modal. | **3D Secure E2E Example:**  typescript

``` test('complete 3DS payment', async ({ page }) => { await page.getByLabel('Card number').fill('4000 0000 0000 3063');
  await page.getByRole('button', { name: 'Pay' }).click();
  
  // Interacting with the Stripe 3DS iframe const iframe = page.frameLocator('iframe[name^="__privateStripeFrame"]');
  await iframe.getByRole('button', { name: 'Complete authentication' }).click();
   await expect(page.getByText('Payment Successful')).toBeVisible();
});

```

Use code with caution.

Copied to clipboard

3. Network Mocking: `page.route` vs. MSW 

* **`page.route`**: Recommended for **pure browser-side mocking** of third-party dependencies you don't control. It is built-in and requires no extra setup.
* **MSW (Mock Service Worker)**: Best for sharing mocks between **unit (Jest/Vitest)** and **E2E (Playwright)** tests. In 2026, use `@mswjs/playwright` for a native integration that handles both HTTP and WebSockets. 

4. Auth Reuse: Storage State & Global Setup `[4][5][6]`

The modern approach is using **Project Dependencies** instead of the legacy `globalSetup` config. This allows for better reporting and trace recording. 

1. **Create Setup Project** in `playwright.config.ts`:
  typescript
  

``` projects: [
  { name: 'setup', testMatch: /auth\.setup\.ts/ },
  { name: 'chromium', use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' }, dependencies: ['setup'],
  },
]

```
  Use code with caution.

Copied to clipboard

2. **Authentication Setup** (`auth.setup.ts`):
  typescript
  

``` import { test as setup } from '@playwright/test';
setup('authenticate', async ({ page }) => { await page.goto('/login');
  await page.fill('#user', 'admin');
  await page.click('#submit');
  await page.context().storageState({ path: 'playwright/.auth/user.json' });
});

```
  Use code with caution.

Copied to clipboard

 

5. CI Sharding & Parallel Workers `[1][2][3]`

Playwright parallelizes tests by default within a machine using **workers**. For large suites, use **sharding** to split tests across multiple CI machines. 

* **Command**: `npx playwright test --shard=1/3` (runs the first third of your suite).
* **Best Practice**: Use **Linux** on CI for cost-efficiency and only install the browsers you need (e.g., `npx playwright install chromium`) to save time. 

Are you looking for a specific **GitHub Actions** configuration to automate this sharding and merge your reports? 

AI can make mistakes, so double-check responses

Copy

Creating a public link...

You can now share this thread with others

Good response

Bad response

Thank you

Your feedback helps Google improve. See our [Privacy Policy](https://policies.google.com/privacy?hl=en).

Share more feedbackReport a problemClose

---

## Sources:

[1] Playwright Best Practices: Writing Resilient and Maintainable Tests. Opens in new tab.  
https://www.linkedin.com/pulse/playwright-best-practices-writing-resilient-tests-serhii-kizenko-40w5f

[2] Best Practices - Playwright. Opens in new tab.  
https://playwright.dev/docs/best-practices#:~:text=Automated%20tests%20should%20verify%20that,easier%20to%20read%20and%20maintain.

[3] Test card numbers - Stripe Documentation. Opens in new tab.  
https://docs.stripe.com/testing?locale=en-GB#:~:text=Simulate%20a%20declined%20payment,provide%20any%20three%2Ddigit%20CVC.&text=You%20can't%20attach%20cards,listed%20in%20the%20following%20table.&text=Attaching%20this%20card%20to%20a,to%20charge%20the%20customer%20fail.

[4] Playwright Best Practices: Writing Resilient and Maintainable Tests. Opens in new tab.  
https://www.linkedin.com/pulse/playwright-best-practices-writing-resilient-tests-serhii-kizenko-40w5f

[5] Best Practices - Playwright. Opens in new tab.  
https://playwright.dev/docs/best-practices#:~:text=Automated%20tests%20should%20verify%20that,easier%20to%20read%20and%20maintain.

[6] Test card numbers - Stripe Documentation. Opens in new tab.  
https://docs.stripe.com/testing?locale=en-GB#:~:text=Simulate%20a%20declined%20payment,provide%20any%20three%2Ddigit%20CVC.&text=You%20can't%20attach%20cards,listed%20in%20the%20following%20table.&text=Attaching%20this%20card%20to%20a,to%20charge%20the%20customer%20fail.

[7] Playwright Best Practices: Writing Resilient and Maintainable Tests. Opens in new tab.  
https://www.linkedin.com/pulse/playwright-best-practices-writing-resilient-tests-serhii-kizenko-40w5f

[8] Best Practices - Playwright. Opens in new tab.  
https://playwright.dev/docs/best-practices#:~:text=Automated%20tests%20should%20verify%20that,easier%20to%20read%20and%20maintain.

[9] Test card numbers - Stripe Documentation. Opens in new tab.  
https://docs.stripe.com/testing?locale=en-GB#:~:text=Simulate%20a%20declined%20payment,provide%20any%20three%2Ddigit%20CVC.&text=You%20can't%20attach%20cards,listed%20in%20the%20following%20table.&text=Attaching%20this%20card%20to%20a,to%20charge%20the%20customer%20fail.

[10] Playwright Best Practices: Writing Resilient and Maintainable Tests. Opens in new tab.  
https://www.linkedin.com/pulse/playwright-best-practices-writing-resilient-tests-serhii-kizenko-40w5f

[11] Best Practices - Playwright. Opens in new tab.  
https://playwright.dev/docs/best-practices#:~:text=Automated%20tests%20should%20verify%20that,easier%20to%20read%20and%20maintain.

[12] Test card numbers - Stripe Documentation. Opens in new tab.  
https://docs.stripe.com/testing?locale=en-GB#:~:text=Simulate%20a%20declined%20payment,provide%20any%20three%2Ddigit%20CVC.&text=You%20can't%20attach%20cards,listed%20in%20the%20following%20table.&text=Attaching%20this%20card%20to%20a,to%20charge%20the%20customer%20fail.

[13] Playwright Best Practices: Writing Resilient and Maintainable Tests. Opens in new tab.  
https://www.linkedin.com/pulse/playwright-best-practices-writing-resilient-tests-serhii-kizenko-40w5f

[14] Best Practices - Playwright. Opens in new tab.  
https://playwright.dev/docs/best-practices#:~:text=Automated%20tests%20should%20verify%20that,easier%20to%20read%20and%20maintain.

[15] Test card numbers - Stripe Documentation. Opens in new tab.  
https://docs.stripe.com/testing?locale=en-GB#:~:text=Simulate%20a%20declined%20payment,provide%20any%20three%2Ddigit%20CVC.&text=You%20can't%20attach%20cards,listed%20in%20the%20following%20table.&text=Attaching%20this%20card%20to%20a,to%20charge%20the%20customer%20fail.

