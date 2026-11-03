# Test bundle end-to-end scenario

The bundle-flow browser test uses the demo organization and two seeded bundles. Start the app and prepare the demo data from the repository root:

```powershell
docker compose up --build -d
docker compose exec backend python manage.py seed_demo_organization
docker compose exec backend python manage.py seed_real_questionnaires
docker compose exec backend python manage.py seed_dummy_questionnaire
```

Run the scenario from `e2e`:

```powershell
npm run test:bundle-flow
```

The scenario selects `dummy-bundle`, saves an answer, reloads and resumes, completes both stages, checks the completed state and report, verifies that a retake is rejected, then starts `prodex-v1` and checks that its progress and report state remain independent.

The backend tests create their own organizations, questionnaire versions, and bundles, so they do not need seeded database rows. Run the bundle-flow test in the backend container from the repository root:

```powershell
docker compose exec backend python -m pytest apps/participants/test_bundle_flow.py -q
```
