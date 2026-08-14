<img width="952" height="451" alt="Stock Ledger Report" src="https://github.com/user-attachments/assets/f447743a-b771-4c1e-91d0-890c63e59761" />
<img width="957" height="447" alt="Stock Ledger Entry Doctype" src="https://github.com/user-attachments/assets/4aa83af2-3df1-43a4-8ebe-38ccc1db3d13" />
<img width="953" height="474" alt="Stock Entry Doctype" src="https://github.com/user-attachments/assets/9ee3dd26-1943-4f63-907a-a822a13bc756" />
<img width="956" height="439" alt="Stock Balance Report" src="https://github.com/user-attachments/assets/38ad8166-4b6b-48e2-adcb-e944ef780f17" />
<img width="959" height="435" alt="Warehouse Management Doctype List" src="https://github.com/user-attachments/assets/36e35bc7-3d8d-4879-9ca0-df36d0cb7a72" />
### Warehouse Management

A warehouse stock management application.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app warehouse_management
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/warehouse_management
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
