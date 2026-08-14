(function () {
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const EVALUATION_TASK_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/task-catalog';
  const GRANT_HOST_ID = 'admin-evaluation-grants';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  let evaluationTaskCatalog = [];

  function escapeHtml(value) {