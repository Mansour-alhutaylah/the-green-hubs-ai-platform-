/** The single factual line every not-yet-available module shows, so the
 * MVP/future boundary reads identically on each of them rather than as N
 * differently-worded promises. */
const LATER_RELEASE_NOTICE =
  'This capability is not included in the current MVP scope and will be activated in a later release.';

/**
 * English string anchors. Voice law (Appendix B): institutional,
 * declarative, never apologetic, never cute — no exclamation marks
 * anywhere. Terminology is locked: "Hub Zero" (never "the AI"/"assistant"/
 * "bot"), "insight", "extraction", "run", "evidence", "hub".
 */
export const en = {
  'brand.mission': 'The operating system for sustainability.',
  'brand.name': 'The Green Hubs',
  'shell.skipToContent': 'Skip to main content',
  'shell.nav.title': 'Navigation',
  'shell.nav.open': 'Open navigation',
  'shell.nav.close': 'Close navigation',

  'nav.dashboard': 'Dashboard',
  'nav.reports': 'Reports',
  'nav.documents': 'Documents',
  'nav.upload': 'Upload',
  'nav.analysis': 'Analysis',
  'nav.hubZero': 'Hub Zero',
  'nav.carbon': 'Carbon Intelligence',
  'nav.telemetry': 'Telemetry',
  'nav.organizations': 'Organizations',
  'nav.users': 'Users & Roles',
  'nav.frameworks': 'Frameworks & Compliance',
  'nav.audit': 'Audit Log',
  'nav.settings': 'Settings',
  'nav.notifications': 'Notifications',
  'nav.profile': 'Profile',
  'nav.soon': 'Soon',
  'nav.domain.oversight': 'Oversight',
  'nav.domain.operations': 'Operations',
  'nav.domain.intelligence': 'Intelligence',
  'nav.domain.administration': 'Administration',

  /* Browser-title segments for the routes that have no short name of their
     own elsewhere in this dictionary (DocumentTitle.tsx reuses `nav.*` and
     the auth page headings for the rest). Detail routes stay generic on
     purpose — a document's own name must not reach the browser title. */
  'title.signIn': 'Sign in',
  'title.forgotPassword': 'Reset password',
  'title.resetPassword': 'New password',
  'title.invite': 'Accept invitation',
  'title.report': 'Report',
  'title.document': 'Document',
  'title.analysisRun': 'Analysis run',
  'title.organization': 'Organization',
  'title.notFound': 'Page not found',

  'sovereignty.line1': 'Secure sustainability workspace',
  'sovereignty.line2': 'Protected document processing',

  'auth.signin.eyebrow': 'Sign in',
  'auth.signin.title': 'Welcome back',
  'auth.signin.supporting': 'Sign in to continue to your workspace.',
  'auth.signin.emailLabel': 'Work email',
  'auth.signin.emailPlaceholder': 'name@company.com',
  'auth.signin.passwordLabel': 'Password',
  'auth.signin.passwordPlaceholder': 'Enter your password',
  'auth.signin.showPassword': 'Show password',
  'auth.signin.hidePassword': 'Hide password',
  'auth.signin.rememberMe': 'Remember me',
  'auth.signin.submit': 'Sign in',
  'auth.welcome.title': 'Sustainability intelligence, grounded in evidence.',
  'auth.welcome.supporting':
    'Manage documents, analyses, and evidence-grounded insights in one secure workspace.',
  'auth.copyright': '© 2026 The Green Hubs. All rights reserved.',
  'auth.preview.title': 'Preview workspace',
  'auth.preview.supporting': 'This build renders demonstration data only.',
  'auth.preview.notice':
    'No account, password, or verification is used here. Entering the Preview workspace creates a local demonstration session and contacts no external service.',
  'auth.preview.enter': 'Enter Preview workspace',
  'auth.signin.forgotPassword': 'Forgot password?',
  'auth.localeToggle': 'العربية',
  'auth.errors.invalidCredentials': 'That email and password combination is not recognized.',
  'auth.errors.rateLimited': 'Too many attempts. Try again in {seconds}s.',
  'auth.errors.expiredInvite': 'This invitation has expired.',
  'auth.errors.expiredInvite.action': 'Request new invite',

  /* The only surviving verification-code string. It labels the individual
     cells of the `OtpCells` visual primitive, which is currently unused —
     no flow in the product asks for a code, and multi-factor
     authentication is not implemented. */
  'auth.otp.digitLabel': 'Digit {position} of {total}',

  'auth.forgot.eyebrow': 'Account recovery',
  'auth.forgot.title': 'Reset your password',
  'auth.forgot.supporting':
    "Enter your work email and we'll send you instructions to reset your password.",
  'auth.forgot.emailLabel': 'Work email',
  'auth.forgot.submit': 'Send reset link',
  'auth.forgot.checkInbox.title': 'Check your inbox',
  'auth.forgot.checkInbox.body': 'If an account exists for {email}, a reset link is on its way.',
  'auth.forgot.backToLogin': 'Back to sign in',

  'auth.reset.eyebrow': 'New password',
  'auth.reset.title': 'Create a new password',
  'auth.reset.supporting': "Choose a strong password you haven't used before on this platform.",
  'auth.reset.passwordLabel': 'New password',
  'auth.reset.confirmPasswordLabel': 'Confirm password',
  'auth.reset.submit': 'Update password',
  'auth.reset.requirement.length': 'At least 8 characters',
  'auth.reset.requirement.uppercase': 'One uppercase letter',
  'auth.reset.requirement.number': 'One number',
  'auth.reset.passwordMismatch': "Passwords don't match.",

  'auth.invite.eyebrow': 'Invitation',
  'auth.invite.unavailable.title': 'Invitations are not available yet',
  'auth.invite.unavailable.supporting':
    'Accepting an invitation from this link is not connected to a backend service yet.',
  'auth.invite.unavailable.notice':
    'No account is created and no credential is collected on this screen. Ask your administrator to create your account, then sign in with your work email and password.',
  'auth.invite.unavailable.signIn': 'Go to sign in',

  'auth.sessionExpired.eyebrow': 'Session',
  'auth.sessionExpired.heading': 'Session expired',
  'auth.sessionExpired.supporting':
    'For your security, your session ended after a period of inactivity. Sign in again to continue.',
  'auth.sessionExpired.cta': 'Sign in again',

  'auth.accessDenied.eyebrow': 'Access',
  'auth.accessDenied.heading': 'Access denied',
  'auth.accessDenied.supporting':
    "You don't have permission to view this. Contact your administrator if you believe this is a mistake.",
  'auth.accessDenied.cta': 'Back to sign in',

  'errors.notFound.title': 'This page does not exist',
  'errors.notFound.body': 'The route you followed has no corresponding page.',
  'errors.noAccess.title': 'This area is not available to your role',
  'errors.noAccess.body': 'Ask an administrator if you believe this is a mistake.',
  'errors.backToDashboard': 'Back to dashboard',
  'errors.routeCrash.title': 'This page hit an error',
  'errors.routeCrash.body': 'Try reloading. If the problem continues, contact your administrator.',

  'stub.laterPhase': LATER_RELEASE_NOTICE,

  'preview.ribbon.label': 'Preview',
  'preview.ribbon.demonstration':
    'Everything shown here is demonstration data, and every action is a demonstration.',
  'preview.ribbon.notProduction': 'This build is not connected to Production.',

  'dashboard.sampleData': 'Sample data · Demo workspace',
  'dashboard.unavailable.title': 'Dashboard metrics are not connected yet',
  'dashboard.unavailable.description':
    'No workspace metrics, activity, or queue data is shown because no service provides them yet. Nothing on this screen is estimated or filled in.',
  'dashboard.unavailable.detail':
    'Documents, upload, and document-level analysis are connected and available from the navigation.',
  'dashboard.state.empty.title': 'Nothing in this workspace yet',
  'dashboard.state.empty.description': 'Upload a document to begin.',
  'dashboard.state.error.title': 'Workspace metrics could not be loaded',
  'dashboard.state.error.description': 'Reload the page to try again.',
  'dashboard.state.forbidden.title': 'You do not have access to workspace metrics',
  'dashboard.state.forbidden.description': 'Ask an administrator if you believe this is a mistake.',
  'dashboard.state.partial': 'Some sections have no data yet.',
  'dashboard.hero.eyebrow': 'Sustainability intelligence',
  'dashboard.hero.welcome': 'Welcome back, {name}',
  'dashboard.hero.description':
    'A clear view of your sustainability evidence, processing activity, and reporting readiness.',
  'dashboard.hero.workspace': 'Demo workspace overview',
  'dashboard.hero.documentsTracked': 'Documents tracked',
  'dashboard.hero.analysisRuns': 'Analysis previews',
  'dashboard.hero.workspaceState': 'Workspace state',
  'dashboard.hero.reviewReady': 'Ready for review',
  'dashboard.hero.openDocuments': 'Review documents',
  'dashboard.hero.openAnalysis': 'Explore analysis',
  'dashboard.hero.openUpload': 'Upload document',
  'dashboard.kpi.documentsAnalyzed': 'Documents analyzed',
  'dashboard.kpi.documentsAnalyzed.caption': '+18 this month',
  'dashboard.kpi.activeReports': 'Active reports',
  'dashboard.kpi.activeReports.caption': '2 in review',
  'dashboard.kpi.complianceScore': 'Compliance score',
  'dashboard.kpi.complianceScore.caption': '+4 pts vs last quarter',
  'dashboard.kpi.pendingApprovals': 'Pending approvals',
  'dashboard.kpi.pendingApprovals.caption': 'Needs attention',
  'dashboard.section.recentDocuments': 'Recent documents',
  'dashboard.section.recentAnalysis': 'Recent AI analysis',
  'dashboard.section.recentActivity': 'Recent activity',
  'dashboard.section.complianceStatus': 'Compliance status',
  'dashboard.section.processingQueue': 'Processing queue',
  'dashboard.section.operations': 'Workspace operations',
  'dashboard.section.insights': 'Intelligence signals',
  'dashboard.section.analysisActivity': 'Analysis activity',
  'dashboard.section.analysisSummary': 'Analysis summary',
  'dashboard.viewAll': 'View all',
  'dashboard.chart.monthly': 'Monthly',
  'dashboard.chart.quarterly': 'Quarterly',
  'dashboard.chart.totalRuns': 'Total runs',
  'dashboard.chart.month.jan': 'Jan',
  'dashboard.chart.month.feb': 'Feb',
  'dashboard.chart.month.mar': 'Mar',
  'dashboard.chart.month.apr': 'Apr',
  'dashboard.chart.month.may': 'May',
  'dashboard.chart.month.jun': 'Jun',
  'dashboard.chart.month.jul': 'Jul',
  'dashboard.chart.month.aug': 'Aug',
  'dashboard.chart.month.sep': 'Sep',
  'dashboard.chart.month.oct': 'Oct',
  'dashboard.chart.month.nov': 'Nov',
  'dashboard.chart.month.dec': 'Dec',
  'dashboard.chart.quarter.q1': 'Q1',
  'dashboard.chart.quarter.q2': 'Q2',
  'dashboard.chart.quarter.q3': 'Q3',
  'dashboard.chart.quarter.q4': 'Q4',
  'analysis.status.complete': 'Completed',
  'analysis.status.processing': 'Processing',
  'analysis.status.failed': 'Failed',
  'analysis.status.insufficientEvidence': 'Insufficient evidence',
  'documents.status.pending': 'Pending',
  'documents.status.processing': 'Processing',
  'documents.status.processed': 'Processed',
  'documents.status.failed': 'Failed',
  'documents.eyebrow': 'Source intelligence',
  'documents.subtitle':
    'Review source files, processing journeys, and readiness signals in this presentation-only workspace.',
  'documents.uploadPreview': 'Upload preview',
  'documents.summary.total': 'Total documents',
  'documents.summary.total.detail': 'Sample source library',
  'documents.summary.processed': 'Processed',
  'documents.summary.processed.detail': 'Ready for review',
  'documents.summary.inProgress': 'In progress',
  'documents.summary.inProgress.detail': 'Preview workflow states',
  'documents.summary.needsAttention': 'Needs attention',
  'documents.summary.needsAttention.detail': 'Controlled failure state',
  'documents.table.title': 'Workspace documents',
  'documents.table.description':
    'Every record is local sample content; status combines text, shape, and color.',
  'documents.table.column.document': 'Document',
  'documents.table.column.engagement': 'Engagement',
  'documents.table.column.status': 'Status',
  'documents.table.column.uploaded': 'Uploaded',
  'documents.status.context.pending': 'Waiting in the sample queue',
  'documents.status.context.processing': 'Sample extraction in progress',
  'documents.status.context.processed': 'Ready for sample review',
  'documents.status.context.failed': 'Sample processing needs attention',
  'documents.tabs.all': 'All',
  'documents.search.label': 'Search documents',
  'documents.search.placeholder': 'Search documents…',
  'documents.filter.allEngagements': 'All engagements',
  'documents.filter.label': 'Filter by engagement',
  'documents.pagination.showing': 'Showing {start}–{end} of {total}',
  'documents.pagination.previous': 'Previous page',
  'documents.pagination.next': 'Next page',
  'documents.empty.noResults': 'No documents match your search or filters.',
  'documents.viewAction': 'View {name}',
  'documents.retry': 'Try again',
  'documents.live.subtitle': 'Review your organization’s source files, processing status, and readiness signals.',
  'documents.live.table.description': 'Documents uploaded to your workspace’s engagements.',
  'documents.live.empty.noDocuments.title': 'No documents yet',
  'documents.live.empty.noDocuments.description': 'Upload a PDF to begin building your source library.',
  'documents.live.empty.noEngagements.title': 'No engagements yet',
  'documents.live.empty.noEngagements.description':
    'Documents are organized by engagement. Ask an administrator to create one before uploading.',
  'documents.live.error.title': 'Documents could not be loaded',
  'documents.live.unauthorized.title': 'Your session is no longer valid',
  'documents.live.unauthorized.description': 'Sign in again to continue.',
  'documents.status.context.live.pending': 'Waiting to be processed',
  'documents.status.context.live.processing': 'Extraction in progress',
  'documents.status.context.live.processed': 'Ready for review',
  'documents.status.context.live.failed': 'Processing needs attention',
  'documents.live.chunkCount': '{count} chunks extracted',
  'documents.detail.eyebrow': 'Document intelligence',
  'documents.detail.notFound.title': 'This document could not be found',
  'documents.detail.notFound.description': 'It may have been removed, or you may not have access to it.',
  'documents.detail.backToDocuments': 'Back to documents',
  'documents.detail.error.title': 'This document could not be loaded',
  'documents.detail.timeline.title': 'Processing journey',
  'documents.detail.timeline.description': 'The document’s real processing state, refreshed from the backend.',
  'documents.detail.metadata.title': 'Document metadata',
  'documents.detail.metadata.filename': 'File name',
  'documents.detail.metadata.engagement': 'Engagement',
  'documents.detail.metadata.created': 'Uploaded',
  'documents.detail.metadata.updated': 'Last updated',
  'documents.detail.metadata.extractedText': 'Extracted text',
  'documents.detail.metadata.extractedText.yes': 'Available',
  'documents.detail.metadata.extractedText.no': 'Not yet available',
  'documents.detail.metadata.chunkCount': 'Chunks',
  'documents.detail.metadata.embeddings': 'Embeddings',
  'documents.detail.embeddings.complete': 'Complete ({completed}/{total})',
  'documents.detail.embeddings.inProgress': 'In progress ({completed}/{total})',
  'documents.detail.embeddings.none': 'Not started',
  'documents.detail.refresh': 'Refresh status',
  'documents.detail.process.action': 'Process document',
  'documents.detail.process.error': 'Unable to process this document.',
  'documents.detail.process.submitting': 'Processing…',
  'documents.detail.process.timeout.title': 'Taking longer than expected',
  'documents.detail.process.timeout.description': 'Processing is still running. Refresh to check the latest status.',
  'documents.detail.intelligence.title': 'AI intelligence',
  'documents.detail.intelligence.description':
    'Prepare this document for evidence-grounded analysis.',
  'documents.detail.intelligence.embeddings.title': 'Embeddings',
  'documents.detail.intelligence.embeddings.notStarted': 'Not started',
  'documents.detail.intelligence.embeddings.processing': 'In progress',
  'documents.detail.intelligence.embeddings.completed': 'Completed',
  'documents.detail.intelligence.embeddings.partial': 'Partially complete',
  'documents.detail.intelligence.embeddings.failed': 'Needs attention',
  'documents.detail.intelligence.embeddings.counts': '{completed} of {total} chunk embeddings completed',
  'documents.detail.intelligence.embeddings.failedCount': '{failed} failed',
  'documents.detail.intelligence.embeddings.action': 'Generate embeddings',
  'documents.detail.intelligence.embeddings.retryAction': 'Retry embeddings',
  'documents.detail.intelligence.embeddings.submitting': 'Generating embeddings…',
  'documents.detail.intelligence.embeddings.requiresProcessed':
    'Process the document before generating embeddings.',
  'documents.detail.intelligence.embeddings.error': 'Unable to generate embeddings.',
  'documents.detail.intelligence.embeddings.result.title': 'Latest generation result',
  'documents.detail.intelligence.embeddings.result.totalChunks': 'Total chunks',
  'documents.detail.intelligence.embeddings.result.newlyCompleted': 'Newly completed',
  'documents.detail.intelligence.embeddings.result.alreadyCompleted': 'Already completed',
  'documents.detail.intelligence.embeddings.result.failed': 'Failed',
  'documents.detail.intelligence.embeddings.result.inProgress': 'In progress elsewhere',
  'documents.detail.intelligence.embeddings.result.conflicts': 'Conflicts',
  'documents.detail.intelligence.embeddings.result.partialFailure':
    'Some chunk embeddings failed. Retrying will attempt only the failed chunks.',
  'documents.detail.intelligence.embeddings.result.alreadyDone':
    'Embeddings were already complete for these chunks.',
  'documents.detail.intelligence.analysis.title': 'AI analysis',
  'documents.detail.intelligence.analysis.notStarted': 'Not started',
  'documents.detail.intelligence.analysis.action': 'Run AI analysis',
  'documents.detail.intelligence.analysis.submitting': 'Running analysis…',
  'documents.detail.intelligence.analysis.requiresProcessed':
    'Process the document before running analysis.',
  'documents.detail.intelligence.analysis.requiresEmbeddings':
    'Generate embeddings before running analysis.',
  'documents.detail.intelligence.analysis.partialNote':
    'Some embeddings are incomplete. Analysis uses only the completed ones.',
  'documents.detail.intelligence.analysis.error': 'Unable to run the analysis.',
  'documents.detail.intelligence.analysis.latestLabel': 'Latest run',
  'documents.detail.intelligence.analysis.viewLatest': 'View latest analysis',

  'documents.upload.eyebrow': 'Document intake',
  'documents.upload.live.subtitle': 'Upload a source PDF to an engagement in your workspace.',
  'documents.upload.engagement.title': 'Engagement',
  'documents.upload.engagement.label': 'Engagement',
  'documents.upload.engagement.placeholder': 'Choose an engagement',
  'documents.upload.engagement.single': 'Uploading to {name}',
  'documents.upload.engagement.required': 'Choose an engagement before uploading.',
  'documents.upload.noEngagements.title': 'No engagements yet',
  'documents.upload.noEngagements.description':
    'Documents are organized by engagement. Ask an administrator to create one before uploading.',
  'documents.upload.dropzone.title': 'Select a PDF document',
  'documents.upload.dropzone.support': 'Browse with mouse, touch, or keyboard.',
  'documents.upload.dropzone.safe': 'Only sent to your organization’s workspace',
  'documents.upload.validated': 'VALIDATED',
  'documents.upload.error.invalidType': 'Choose a PDF file. Other formats are not accepted.',
  'documents.upload.error.tooLarge': 'This file is larger than the {size} MB limit.',
  'documents.upload.error.generic': 'Unable to upload this document.',
  'documents.upload.submit': 'Upload document',
  'documents.upload.submitting': 'Uploading…',
  'documents.upload.pdfOnly': 'PDF only',
  'documents.upload.maxSize': '{size} MB max',
  'documents.upload.safeguard.title': 'Upload safeguard',
  'documents.upload.safeguard.description':
    'Do not select confidential material beyond what your organization has approved for this workspace.',

  'analysis.eyebrow': 'Intelligence workspace',
  'analysis.subtitle': 'Review sample analysis journeys and source handling without invoking an AI service.',
  'analysis.sampleBadge': 'Sample data · Analysis preview',
  'analysis.kpi.total': 'Total analyses',
  'analysis.kpi.total.detail': 'Across all preview states',
  'analysis.kpi.completed.detail': 'Ready for human review',
  'analysis.kpi.processing.detail': 'No AI service running',
  'analysis.kpi.failed.detail': 'Controlled preview failure',
  'analysis.kpi.insufficientEvidence.detail': 'Source lacked structured data',
  'analysis.table.title': 'Recent analysis runs',
  'analysis.table.description': 'Source relationship, confidence, and current sample state remain visible together.',
  'analysis.table.column.analysisName': 'Analysis',
  'analysis.table.column.document': 'Document',
  'analysis.table.column.organization': 'Organization',
  'analysis.table.column.status': 'Status',
  'analysis.table.column.date': 'Date',
  'analysis.table.column.confidence': 'Confidence',
  'analysis.tabs.all': 'All',
  'analysis.search.label': 'Search analysis runs',
  'analysis.search.placeholder': 'Search analysis runs…',
  'analysis.filter.allOrganizations': 'All organizations',
  'analysis.filter.label': 'Filter by organization',
  'analysis.pagination.showing': 'Showing {start}–{end} of {total}',
  'analysis.pagination.previous': 'Previous page',
  'analysis.pagination.next': 'Next page',
  'analysis.empty.noResults': 'No analysis runs match your search or filters.',
  'analysis.viewAction': 'View {name}',
  'analysis.sourceDocument': 'Source document',
  'analysis.startedAt': 'Started {date}',
  'analysis.sampleConfidence': 'Sample confidence',
  'analysis.states.eyebrow': 'Interface states',
  'analysis.states.title': 'Workflow state preview',
  'analysis.states.noAnalysis.title': 'No analysis yet',
  'analysis.states.noAnalysis.description': 'A connected workflow will show eligible documents here.',
  'analysis.states.processing.label': 'Sample processing',
  'analysis.states.processing.description': 'Sample analysis is processing',
  'analysis.states.notAvailable.title': 'Analysis not available',
  'analysis.states.notAvailable.description': 'Unsupported files remain visible with a clear reason.',
  'analysis.live.subtitle':
    'Run analyses from a processed document and review their evidence-grounded results.',
  'analysis.live.noHistory.title': 'Analysis history is not available yet',
  'analysis.live.noHistory.description':
    'Analysis is currently launched from a processed document. A dedicated analysis history view will be added in a later MVP scope.',
  'analysis.live.noHistory.action': 'Go to documents',
  'analysis.run.eyebrow': 'Analysis intelligence',
  'analysis.run.live.title': 'Sustainability summary',
  'analysis.run.live.completedAt': 'Completed {date}',
  'analysis.run.live.startedAt': 'Started {date}',
  'analysis.run.loading': 'Loading analysis run',
  'analysis.run.notFound.title': 'This analysis run could not be found',
  'analysis.run.notFound.description': 'It may have been removed, or you may not have access to it.',
  'analysis.run.error.title': 'This analysis run could not be loaded',
  'analysis.run.backToDocuments': 'Back to documents',
  'analysis.run.viewSourceDocument': 'View source document',
  'analysis.run.refresh': 'Refresh status',
  'analysis.run.processing.title': 'Analysis in progress',
  'analysis.run.processing.description': 'The analysis run is processing. Results appear here when it completes.',
  'analysis.run.processing.timeout.title': 'Taking longer than expected',
  'analysis.run.processing.timeout.description': 'The analysis is still running. Refresh to check the latest status.',
  'analysis.run.failed.title': 'The analysis could not be completed',
  'analysis.run.failed.description': 'No result was produced for this run.',
  'analysis.run.failed.retryAction': 'Run analysis again',
  'analysis.run.failed.retrying': 'Running analysis…',
  'analysis.run.insufficient.title': 'Not enough supporting evidence',
  'analysis.run.insufficient.description':
    'The document did not provide enough supporting evidence for this analysis. This is a valid outcome, not a system failure.',
  'analysis.run.insufficient.reasonTitle': 'Why evidence was insufficient',
  'analysis.run.unknownStatus.title': 'Unrecognized run state',
  'analysis.run.unknownStatus.description':
    'This run is in a state this interface does not recognize. Refresh to check the latest status.',
  'analysis.run.result.unavailable.title': 'Result data unavailable',
  'analysis.run.result.unavailable.description':
    'This run is completed, but its structured result could not be displayed.',
  'analysis.run.summary.title': 'Executive summary',
  'analysis.run.summary.description': 'Generated from evidence retrieved from this document.',
  'analysis.run.overview.reportingPeriod': 'Reporting period',
  'analysis.run.overview.notStated': 'Not stated in the document',
  'analysis.run.overview.topics': 'Detected topics',
  'analysis.run.confidence.label': 'Model confidence',
  'analysis.run.confidence.detail': 'Reported by the analysis output',
  'analysis.run.confidence.note': 'Not evaluation-calibrated',
  'analysis.run.metrics.title': 'Reported metrics',
  'analysis.run.metrics.description': 'Values appear only when the document states them.',
  'analysis.run.metrics.stated': 'Stated',
  'analysis.run.metrics.notStated': 'Not stated',
  'analysis.run.metrics.uncertain': 'Uncertain',
  'analysis.run.metrics.noValue': 'No value stated in the document',
  'analysis.run.metrics.period': 'Period: {period}',
  'analysis.run.metrics.empty': 'No metrics were reported in this analysis.',
  'analysis.run.findings.title': 'Key findings',
  'analysis.run.findings.description': 'Each finding is linked to its cited sources.',
  'analysis.run.findings.label': 'Finding {number}',
  'analysis.run.findings.empty': 'No findings were produced by this analysis.',
  'analysis.run.recommendations.title': 'Recommendations',
  'analysis.run.recommendations.description': 'Suggested next steps grounded in the cited evidence.',
  'analysis.run.recommendations.empty': 'No recommendations were produced by this analysis.',
  'analysis.run.sources.label': 'Sources: {numbers}',
  'analysis.run.citations.title': 'Cited sources',
  'analysis.run.citations.description': 'Excerpts retrieved from the document and stored with this run.',
  'analysis.run.citations.source': 'Source {number}',
  'analysis.run.citations.chunk': 'Chunk {index}',
  'analysis.run.citations.chars': 'Characters {start}–{end}',
  'analysis.run.citations.relevance': 'Relevance {score}',
  'analysis.run.citations.expand': 'Show excerpt',
  'analysis.run.citations.empty': 'No citations were stored for this run.',
  'dashboard.status.analyzed': 'Analyzed',
  'dashboard.status.processing': 'Processing',
  'dashboard.status.queued': 'Queued',
  'dashboard.status.failed': 'Failed',
  'dashboard.status.onTrack': 'On track',
  'dashboard.status.needsReview': 'Needs review',
  'dashboard.activity.uploaded': '{actor} uploaded {doc}',
  'dashboard.activity.approved': '{actor} approved {doc}',
  'dashboard.activity.viewed': '{actor} viewed {doc}',
  'dashboard.activity.published': '{actor} published {doc}',
  'dashboard.activity.latest': 'Latest activity',
  'dashboard.activity.history': 'Workspace history',
  'dashboard.kpi.value.percentage': '{value}%',
  'dashboard.insight.extracted': '{figures} figures extracted, {flagged} flagged for review',
  'dashboard.insight.processing': 'Running extraction — {percent}% complete',
  'dashboard.insight.queued': 'Queued for analysis',
  'dashboard.insight.failed': 'Analysis did not complete',
  'dashboard.queue.eta': 'ETA ~{minutes} min',
  'dashboard.queue.empty': 'The processing queue is empty.',

  'placeholder.eyebrow': 'Coming soon',
  'placeholder.notify': 'Notify me when available',
  'placeholder.hubZero.description':
    'Insight Ledger, approval queue, and explainability for every extracted figure.',
  'placeholder.hubZero.unlock': LATER_RELEASE_NOTICE,
  'placeholder.carbon.description': 'Scope 1, 2 and 3 ledgers with Saudi factor libraries.',
  'placeholder.carbon.unlock': LATER_RELEASE_NOTICE,
  'placeholder.telemetry.description': 'Live IIoT, meter, and drone sources, facility by facility.',
  'placeholder.telemetry.unlock': LATER_RELEASE_NOTICE,
  'placeholder.frameworks.description': 'Framework mappings across GRI, CSRD, and Saudi standards.',
  'placeholder.frameworks.unlock': LATER_RELEASE_NOTICE,
  'placeholder.audit.description': 'A full audit trail of who touched what, and when.',
  'placeholder.audit.unlock': LATER_RELEASE_NOTICE,

  'contextBar.search.unavailable': 'Search — coming later',
  'contextBar.orgSwitcher.label': 'Switch organization',
  'contextBar.notifications.empty': "You're all caught up.",
  'contextBar.profile.profile': 'Profile',
  'contextBar.profile.settings': 'Settings',
  'contextBar.profile.signOut': 'Sign out',

  'coachmarks.orgSwitcher': 'Switch between the organizations you belong to here.',
  'coachmarks.insightLedger': 'Hub Zero will annotate your numbers here once it is activated in a later release.',
  'coachmarks.uploadEntry': 'Upload sustainability documents to begin analysis.',
  /* Compact-viewport presentation only. Above 480px the tips appear on
     arrival and need no trigger, heading, or close control. */
  'coachmarks.trigger': 'Getting started',
  'coachmarks.title': 'Getting started',
  'coachmarks.close': 'Close getting started tips',
  'coachmarks.dismiss': 'Got it, do not show again',
  /* ---------------------------------------------------------------- *
   * F2A — core operating pages                                        *
   * ---------------------------------------------------------------- */

  'nav.engagements': 'Engagements',
  'title.engagement': 'Engagement',

  /* The shared non-populated-state vocabulary. Every F2A page renders
     these through `StateBlock`, so "we could not load this", "you may not
     see this", "that does not exist", and "there is nothing here" read as
     four distinct answers on every screen rather than one grey box. */
  'workspace.state.loading': 'Loading',
  'workspace.state.error.title': 'This could not be loaded',
  'workspace.state.error.description':
    'The request did not complete. Nothing on this screen is estimated or filled in while it is missing.',
  'workspace.state.retry': 'Try again',
  'workspace.state.forbidden.title': 'You do not have access to this',
  'workspace.state.forbidden.description': 'Ask an administrator if you believe this is a mistake.',
  'workspace.state.notFound.title': 'This record could not be found',
  'workspace.state.notFound.description':
    'It may have been removed, or it may belong to another organization.',
  'workspace.state.partial':
    'Part of this workspace could not be loaded. Everything shown is real; anything missing is marked as unavailable rather than filled in.',
  'workspace.value.unavailable': 'Unavailable',
  'workspace.value.unavailable.detail': 'This figure could not be loaded. It is not zero.',
  'workspace.value.notRecorded': 'Not recorded',

  /* Live dashboard. Every figure here is a `total` the backend computed;
     the unavailable lines below name the capabilities no endpoint
     provides, which are stated rather than estimated. */
  'dashboard.live.eyebrow': 'Workspace overview',
  'dashboard.live.subtitle':
    'Exact figures from your organization’s documents and engagements. Capabilities with no service behind them are named, not estimated.',
  'dashboard.live.section.totals': 'Workspace totals',
  'dashboard.live.section.processing': 'Document processing',
  'dashboard.live.section.notConnected': 'Not provided by the product API',
  'dashboard.live.card.documentsTotal': 'Documents',
  'dashboard.live.card.documentsTotal.detail': 'Exact total across your organization',
  'dashboard.live.card.engagementsTotal': 'Engagements',
  'dashboard.live.card.engagementsTotal.detail': 'Exact total across your organization',
  'dashboard.live.card.organization': 'Organization',
  'dashboard.live.card.organization.detail': 'Resolved from your account',
  'dashboard.live.processing.description':
    'Each count is the exact number of documents in that state, read from the documents service.',
  'dashboard.live.recentDocuments.title': 'Recent documents',
  'dashboard.live.recentDocuments.description':
    'The five most recently created documents in your organization.',
  'dashboard.live.recentDocuments.empty': 'No documents have been uploaded yet.',
  'dashboard.live.empty.title': 'This workspace has no documents yet',
  'dashboard.live.empty.description': 'Upload a document to begin building your source library.',
  'dashboard.live.error.title': 'The dashboard could not be loaded',
  'dashboard.live.error.description':
    'No figures are shown, because an estimate in place of a measurement would be worse than nothing.',
  'dashboard.live.unavailable.description':
    'No service provides this yet, so nothing is shown for it. It is not zero and it is not empty.',
  'dashboard.live.unavailable.evidenceReview': 'Evidence review',
  'dashboard.live.unavailable.activity': 'Activity feed',
  'dashboard.live.unavailable.readiness': 'Reporting readiness',
  'dashboard.live.unavailable.processingQueue': 'Processing queue',
  'dashboard.live.viewDocuments': 'View documents',
  'dashboard.live.viewEngagements': 'View engagements',

  /* Preview-only dashboard breakdowns (synthetic, ribbon-labelled). */
  'dashboard.preview.section.documentStates': 'Documents by processing state',
  'dashboard.preview.section.evidenceReview': 'Evidence review',
  'dashboard.preview.section.engagements': 'Engagements',
  'dashboard.preview.section.readiness': 'Reporting readiness',
  'dashboard.preview.evidence.pendingReview': 'Pending review',
  'dashboard.preview.evidence.approved': 'Approved',
  'dashboard.preview.evidence.rejected': 'Rejected',
  'dashboard.preview.evidence.withdrawn': 'Withdrawn',
  'dashboard.preview.evidence.note':
    'A demonstration of the review lifecycle’s states. No review action is available in this release.',
  'dashboard.preview.engagements.total': 'Total engagements',
  'dashboard.preview.readiness.label': 'Demonstration readiness',
  'dashboard.preview.readiness.detail': 'Synthetic figure — not a compliance assessment.',

  /* Organizations. */
  'organizations.eyebrow': 'Administration',
  'organizations.subtitle': 'Your organization as the product API reports it.',
  'organizations.preview.subtitle':
    'A synthetic organization, shown so the screen’s states can be reviewed without a backend.',
  'organizations.table.caption': 'Organizations in your workspace',
  'organizations.table.column.name': 'Organization',
  'organizations.table.column.created': 'Created',
  'organizations.table.column.actions': 'Details',
  'organizations.view': 'View {name}',
  'organizations.open': 'Open',
  'organizations.empty.title': 'No organization is linked to your account',
  'organizations.empty.description':
    'Your account has not been attached to an organization yet. An administrator provisions this outside the application.',
  'organizations.error.title': 'Organizations could not be loaded',
  'organizations.create.unavailable.title': 'Creating an organization is not available',
  'organizations.create.unavailable.description':
    'The product API rejects every organization-creation request in this release. Organizations are provisioned outside this application, so there is no control here that would succeed.',
  'organizations.delete.unavailable':
    'Deleting an organization is not supported by the product API and is not offered here.',
  'organizations.preview.create.action': 'Add organization (Preview only)',
  'organizations.preview.create.notice':
    'This demonstrates the form only. Nothing is saved, nothing leaves this browser, and the entry disappears on reload.',
  'organizations.preview.create.label': 'Organization name',
  'organizations.preview.create.submit': 'Add to this Preview session',
  'organizations.preview.create.added': 'Added to this Preview session only.',
  'organizations.detail.eyebrow': 'Organization',
  'organizations.detail.back': 'Back to organizations',
  'organizations.detail.profile.title': 'Profile',
  'organizations.detail.profile.description':
    'The three fields the product API exposes for an organization. No member count, facility count, or sector is shown, because no endpoint reports one.',
  'organizations.detail.field.name': 'Name',
  'organizations.detail.field.created': 'Created',
  'organizations.detail.rename.title': 'Rename organization',
  'organizations.detail.rename.description':
    'The name is the only field this API allows you to change.',
  'organizations.detail.rename.label': 'Organization name',
  'organizations.detail.rename.submit': 'Save name',
  'organizations.detail.rename.submitting': 'Saving…',
  'organizations.detail.rename.success': 'The organization name was updated.',
  'organizations.detail.rename.error': 'The organization name could not be updated.',
  'organizations.detail.rename.forbidden':
    'Renaming an organization requires an administrator role. The control is not shown because the request would be refused.',
  'organizations.detail.rename.preview':
    'In Preview this form validates and resets. Nothing is saved and no request is sent.',
  'organizations.pagination.showing': 'Showing {start}–{end} of {total}',
  'organizations.pagination.previous': 'Previous page',
  'organizations.pagination.next': 'Next page',

  /* Engagements. */
  'engagements.eyebrow': 'Operations',
  'engagements.subtitle': 'The engagements in your organization, and the work grouped under them.',
  'engagements.preview.subtitle':
    'Synthetic engagements, shown so the screen’s states can be reviewed without a backend.',
  'engagements.table.caption': 'Engagements in your organization',
  'engagements.table.column.title': 'Engagement',
  'engagements.table.column.status': 'Status',
  'engagements.table.column.created': 'Created',
  'engagements.view': 'View {name}',
  'engagements.open': 'Open',
  'engagements.filter.label': 'Filter engagements',
  'engagements.filter.status': 'Status',
  'engagements.filter.allStatuses': 'All statuses',
  'engagements.search.label': 'Search engagements',
  'engagements.search.placeholder': 'Search engagements…',
  'engagements.status.active': 'Active',
  'engagements.status.draft': 'Draft',
  'engagements.status.closed': 'Closed',
  'engagements.status.archived': 'Archived',
  'engagements.status.none': 'No status',
  'engagements.empty.title': 'No engagements yet',
  'engagements.empty.description':
    'Engagements group the documents and analyses for a reporting cycle. Create one to begin.',
  'engagements.empty.noResults': 'No engagements match your search or filters.',
  'engagements.error.title': 'Engagements could not be loaded',
  'engagements.create.action': 'New engagement',
  'engagements.create.title': 'Create an engagement',
  'engagements.create.description':
    'The engagement is created in your own organization. There is no control to choose a different one, and the service refuses any other.',
  'engagements.create.field.title': 'Title',
  'engagements.create.field.title.placeholder': 'Annual disclosure 2026',
  'engagements.create.field.status': 'Status',
  'engagements.create.field.status.default': 'Use the service default',
  'engagements.create.field.status.hint':
    'Left as the default, the service assigns its own starting status.',
  'engagements.create.organization.label': 'Organization',
  'engagements.create.organization.hint':
    'Taken from your signed-in account, as the server resolved it. It is not editable and is never read from the address bar.',
  'engagements.create.organization.missing':
    'Your account is not linked to an organization, so an engagement cannot be created.',
  'engagements.create.submit': 'Create engagement',
  'engagements.create.submitting': 'Creating…',
  'engagements.create.cancel': 'Cancel',
  'engagements.create.success': 'The engagement was created.',
  'engagements.create.error': 'The engagement could not be created.',
  'engagements.create.forbidden':
    'Creating an engagement requires an editor role or above. The control is not shown because the request would be refused.',
  'engagements.create.preview':
    'In Preview this form validates and resets. Nothing is saved and no request is sent.',
  'engagements.detail.eyebrow': 'Engagement',
  'engagements.detail.back': 'Back to engagements',
  'engagements.detail.profile.title': 'Details',
  'engagements.detail.profile.description': 'The fields the product API exposes for an engagement.',
  'engagements.detail.field.title': 'Title',
  'engagements.detail.field.status': 'Status',
  'engagements.detail.field.created': 'Created',
  'engagements.detail.field.organization': 'Organization',
  'engagements.detail.edit.title': 'Edit engagement',
  'engagements.detail.edit.description':
    'Only the title and status can be changed. An engagement cannot be moved to another organization.',
  'engagements.detail.edit.submit': 'Save changes',
  'engagements.detail.edit.submitting': 'Saving…',
  'engagements.detail.edit.success': 'The engagement was updated.',
  'engagements.detail.edit.error': 'The engagement could not be updated.',
  'engagements.detail.edit.forbidden':
    'Editing an engagement requires an editor role or above. The control is not shown because the request would be refused.',
  'engagements.detail.documents.title': 'Documents',
  'engagements.detail.documents.description':
    'Documents are filtered by engagement on the Documents page, which reports the exact total for this engagement.',
  'engagements.detail.documents.action': 'View this engagement’s documents',
  'engagements.detail.delete.unavailable':
    'Deleting an engagement is not supported by the product API and is not offered here.',
  'engagements.pagination.showing': 'Showing {start}–{end} of {total}',
  'engagements.pagination.previous': 'Previous page',
  'engagements.pagination.next': 'Next page',

  /* Users & Roles. */
  'users.eyebrow': 'Administration',
  'users.subtitle': 'Your account and the role the server holds for it.',
  'users.preview.subtitle':
    'A synthetic team directory covering every role tier, shown so the screen can be reviewed without a backend.',
  'users.table.caption': 'People in this workspace',
  'users.table.column.name': 'Name',
  'users.table.column.email': 'Email',
  'users.table.column.role': 'Role',
  'users.role.unrecognized': 'Unrecognized role',
  'users.role.unrecognized.detail':
    'The server holds a role value this interface does not recognize. Every permission is denied for it.',
  'users.you': 'You',
  'users.live.disclosure.title': 'This is your account, not a team directory',
  'users.live.disclosure.description':
    'The product API exposes only the signed-in user’s own profile. A team directory, invitations, and role changes require a user-management contract the backend does not implement, so no such control is shown here and no other person is listed.',
  'users.preview.disclosure.title': 'Synthetic directory',
  'users.preview.disclosure.description':
    'Every person listed here is invented for demonstration. No invitation, role change, or removal is available in any mode.',
  'users.error.title': 'Your account could not be loaded',
  'users.empty.title': 'No account information is available',
  'users.empty.description': 'Sign in again to reload your profile.',

  /* Settings. */
  'settings.eyebrow': 'Administration',
  'settings.subtitle': 'Your account, this workspace, and what this build is connected to.',
  'settings.nav.label': 'Settings sections',
  'settings.section.general': 'General',
  'settings.section.language': 'Language',
  'settings.section.residency': 'Data residency',
  'settings.section.security': 'Security',
  'settings.section.integrations': 'Integrations',
  'settings.section.about': 'About',
  'settings.general.identity.title': 'Your account',
  'settings.general.identity.description': 'As the server resolved it for this session.',
  'settings.general.field.name': 'Name',
  'settings.general.field.email': 'Email',
  'settings.general.field.role': 'Role',
  'settings.general.field.organization': 'Organization',
  'settings.general.organization.missing': 'Not linked to an organization',
  'settings.general.mode.title': 'Application mode',
  'settings.general.mode.live': 'Live',
  'settings.general.mode.preview': 'Preview',
  'settings.general.mode.live.description':
    'This build talks to real services. Every figure shown in the product comes from a real response.',
  'settings.general.mode.preview.description':
    'This build contacts no service. Everything shown in the product is synthetic demonstration data.',
  'settings.language.title': 'Interface language',
  'settings.language.description': 'The language this release of the product is delivered in.',
  'settings.language.label': 'Language',
  'settings.language.english': 'English',
  'settings.language.arabic': 'العربية',
  'settings.language.current': 'Current language',
  'settings.language.onlyOption':
    'English is the only language this release ships. There is no language control here because there is nothing to choose between.',
  'settings.language.future.title': 'Arabic is planned for a future release',
  'settings.language.future.description':
    'Arabic and right-to-left layout are deferred to a dedicated later phase. They are not offered here yet, because a partly translated interface would be harder to trust than an English one.',
  'settings.language.note':
    'When more than one language ships, the choice will be stored in this browser rather than on your account.',
  'settings.residency.title': 'Data residency',
  'settings.residency.unavailable.title': 'Residency metadata is not published',
  'settings.residency.unavailable.description':
    'The product API exposes no data-residency information, so none is shown. This screen will not name a region, a provider, or a hosting location it cannot verify.',
  'settings.security.title': 'Security',
  'settings.security.session.title': 'Session',
  'settings.security.session.signedInAs': 'Signed in as',
  'settings.security.session.method': 'Sign-in method',
  'settings.security.session.method.password': 'Email and password',
  'settings.security.session.method.preview': 'Local Preview session — no credential is used',
  'settings.security.session.expiry':
    'Your session ends after a period of inactivity, and sooner if it is revoked.',
  'settings.security.mfa.title': 'Multi-factor authentication',
  'settings.security.mfa.description':
    'Multi-factor authentication administration is not implemented. This application neither enrols nor verifies a second factor, and no screen here can turn one on.',
  'settings.security.signOut': 'Sign out',
  'settings.integrations.title': 'Integrations',
  'settings.integrations.description':
    'The capabilities this product ships with. No provider, address, account, key name, or credential is shown for any of them, and none is configurable from this application.',
  'settings.integrations.documentStorage': 'Document storage',
  'settings.integrations.documentAnalysis': 'Document analysis',
  'settings.integrations.authentication': 'Authentication',
  'settings.integrations.state.notConfigurable': 'Not configurable here',
  'settings.about.title': 'About',
  'settings.about.appName': 'Application',
  'settings.about.version': 'Version',
  'settings.about.version.unstamped': 'This build carries no version stamp',
  'settings.about.mode': 'Mode',
  'settings.about.environment': 'Build classification',
  'settings.about.environment.unstamped': 'Not declared by this build',
  'settings.about.api': 'Backend API',
  'settings.about.auth': 'Authentication service',
  'settings.about.configured': 'Configured',
  'settings.about.notConfigured': 'Not configured',
  'settings.about.claims':
    'No certification, uptime, availability, or compliance claim is made on this screen.',

  /* ---------------------------------------------------------------- *
   * Executive command centre                                          *
   * ---------------------------------------------------------------- */

  'dashboard.executive.title': 'Evidence command centre',
  'dashboard.executive.subtitle':
    'The condition of your evidence workspace, what needs attention, and what is ready to report.',
  'dashboard.executive.period': 'Reporting period',
  'dashboard.executive.generated': 'Figures as of',
  'dashboard.executive.reviewEvidence': 'Review evidence',
  'dashboard.executive.openReports': 'Open reports',
  'dashboard.executive.uploadSource': 'Upload source',

  'dashboard.kpi.definition': 'What this figure measures: {label}',
  'dashboard.kpi.evidenceReadiness': 'Evidence readiness',
  'dashboard.kpi.evidenceReadiness.definition':
    'The share of source documents that have reached a report-ready state. This describes your evidence, not your regulatory position, and it is not a compliance score.',
  'dashboard.kpi.evidenceReadiness.context': '{ready} of {total} documents report-ready',
  'dashboard.kpi.sourceDocuments': 'Source documents',
  'dashboard.kpi.sourceDocuments.definition':
    'Every document uploaded to this workspace, whatever stage it has reached.',
  'dashboard.kpi.sourceDocuments.context': 'Uploaded for {period}',
  'dashboard.kpi.awaitingReview': 'Awaiting review',
  'dashboard.kpi.awaitingReview.definition':
    'Documents that have been analyzed but not yet verified by a reviewer.',
  'dashboard.kpi.awaitingReview.context': 'Analyzed, not yet verified',
  'dashboard.kpi.processingHealth': 'Processing health',
  'dashboard.kpi.processingHealth.definition':
    'The share of processing attempts that completed without failing. A failure means the document could not be extracted, not that its contents were rejected.',
  'dashboard.kpi.processingHealth.context': '{failures} failed extractions',

  'dashboard.throughput.title': 'Evidence throughput',
  'dashboard.throughput.description': 'Documents reaching verified and report-ready, by month.',
  'dashboard.throughput.empty': 'No throughput has been recorded for this period yet.',
  'dashboard.throughput.summary':
    'Across {months} months of {period}, from {first} to {last}, {verified} documents were verified and {reportReady} reached report-ready.',
  'dashboard.throughput.series.verified': 'Verified',
  'dashboard.throughput.series.reportReady': 'Report-ready',
  'dashboard.throughput.unit': 'Documents per month',
  'dashboard.throughput.axis.month': 'Month',

  'dashboard.action.title': 'Action centre',
  'dashboard.action.description': 'What needs attention, most urgent first.',
  'dashboard.action.empty': 'Nothing needs attention in this workspace.',
  'dashboard.action.severity.critical': 'Critical',
  'dashboard.action.severity.attention': 'Attention',
  'dashboard.action.severity.scheduled': 'Scheduled',
  'dashboard.action.failedExtraction.title': 'Failed extractions need a retry',
  'dashboard.action.failedExtraction.detail':
    'These documents could not be read. Open Documents to retry them.',
  'dashboard.action.awaitingReview.title': 'Evidence awaiting review',
  'dashboard.action.awaitingReview.detail':
    'Analyzed documents that no reviewer has verified yet.',
  'dashboard.action.insufficientEvidence.title': 'Analyses with insufficient evidence',
  'dashboard.action.insufficientEvidence.detail':
    'These runs finished without enough supporting documents to draw on.',
  'dashboard.action.engagementDeadline.title': 'Engagement approaching its reporting date',
  'dashboard.action.engagementDeadline.detail':
    'Review the engagement scope before the reporting period closes.',

  'dashboard.pipeline.title': 'Evidence pipeline',
  'dashboard.pipeline.description':
    'Where documents sit in the lifecycle, and how many have not carried through.',
  'dashboard.pipeline.uploaded': 'Uploaded',
  'dashboard.pipeline.extracted': 'Extracted',
  'dashboard.pipeline.analyzed': 'Analyzed',
  'dashboard.pipeline.verified': 'Verified',
  'dashboard.pipeline.reportReady': 'Report-ready',
  'dashboard.pipeline.dropOff': '{count} did not carry through',

  'dashboard.framework.title': 'Framework evidence coverage',
  'dashboard.framework.description':
    'How much of each framework has supporting evidence attached.',
  'dashboard.framework.empty': 'No framework has been assessed in this workspace yet.',
  'dashboard.framework.covered': '{covered} of {total} disclosures',
  'dashboard.framework.disclaimer':
    'Sample evidence coverage only. This states how many disclosures have a verified document attached in this demonstration workspace. It is not a compliance assessment, an assurance opinion, or a certification.',

  /* ---------------------------------------------------------------- *
   * Reports                                                           *
   * ---------------------------------------------------------------- */

  'reports.eyebrow': 'Reporting',
  'reports.preview.subtitle':
    'A demonstration reporting workspace. Every report below is sample data, and nothing here is filed, exported, or sent anywhere.',
  'reports.live.subtitle': 'Reporting for this workspace.',

  'reports.table.caption': 'Reports',
  'reports.table.description': 'Reports for {period}.',
  'reports.table.column.name': 'Report',
  'reports.table.column.framework': 'Framework',
  'reports.table.column.status': 'Status',
  'reports.table.column.readiness': 'Readiness',
  'reports.table.column.owner': 'Owner',
  'reports.table.column.updated': 'Last updated',

  'reports.filter.label': 'Filter reports',
  'reports.filter.framework': 'Filter by framework',
  'reports.filter.status': 'Filter by status',
  'reports.filter.allFrameworks': 'All frameworks',
  'reports.filter.allStatuses': 'All statuses',
  'reports.search.label': 'Search reports',
  'reports.search.placeholder': 'Report or owner',

  'reports.framework.gri': 'GRI',
  'reports.framework.csrd': 'CSRD',
  'reports.framework.issb': 'ISSB',
  'reports.framework.internal': 'Internal',

  'reports.status.draft': 'Draft',
  'reports.status.inReview': 'In review',
  'reports.status.readyToPublish': 'Ready to publish',
  'reports.status.published': 'Published',

  'reports.total.all': 'Reports',
  'reports.total.readyToPublish': 'Ready to publish',
  'reports.total.inReview': 'In review',
  'reports.total.averageReadiness': 'Average readiness',

  'reports.empty.title': 'No reports yet',
  'reports.empty.description':
    'Reports appear here once evidence has been gathered against a framework.',
  'reports.empty.noMatches': 'No report matches these filters.',
  'reports.unavailable.title': 'Reporting is not connected',
  'reports.unavailable.description':
    'This product exposes no reporting service yet, so there is nothing to list. This is not an empty workspace: the product cannot tell how many reports exist.',

  'reports.templates.title': 'Report templates',
  'reports.templates.description':
    'Starting points for a new report. Selecting one in this demonstration creates nothing.',
  'reports.templates.sections': '{count} sections',
  'reports.template.gri.name': 'GRI Core disclosure set',
  'reports.template.gri.description':
    'Universal and topic-specific disclosures for an annual sustainability statement.',
  'reports.template.csrd.name': 'CSRD ESRS reporting set',
  'reports.template.csrd.description':
    'European Sustainability Reporting Standards structure, environment through governance.',
  'reports.template.issb.name': 'ISSB S2 climate set',
  'reports.template.issb.description':
    'Governance, strategy, risk management, and metrics for climate-related disclosure.',
  'reports.template.internal.name': 'Internal quarterly review',
  'reports.template.internal.description':
    'A short internal summary of site performance for a single quarter.',

  'reports.generate.action': 'Generate preview',
  'reports.generate.notice':
    'Demonstration only. No report was generated, nothing was saved, and no request was sent. This notice clears when the page reloads.',
  'reports.export.action': 'Export',
  'reports.export.notice':
    'Demonstration only. No file was created and nothing was downloaded. Export needs a reporting service, which this product does not have yet.',

  'reports.detail.eyebrow': 'Report',
  'reports.detail.subtitle': 'A single report and the evidence behind it.',
  'reports.detail.backToList': 'All reports',
  'reports.detail.profile.title': 'Report profile',
  'reports.detail.profile.description': 'What this report covers and who owns it.',
  'reports.detail.field.period': 'Reporting period',
  'reports.detail.sections.title': 'Sections and evidence',
  'reports.detail.sections.description':
    'How much supporting evidence each section has, and which sections are still short.',
  'reports.detail.sections.evidence': '{count} evidence documents',
  'reports.detail.sections.complete': 'Evidence attached',
  'reports.detail.sections.incomplete': 'Needs evidence',
  'reports.detail.actions.title': 'Actions',
  'reports.detail.actions.description':
    'Demonstration actions. Neither writes a file nor sends a request.',

  /* ---------------------------------------------------------------- *
   * Settings workspace                                                *
   * ---------------------------------------------------------------- */

  'settings.nav.select': 'Settings section',
  'settings.section.overview': 'Overview',
  'settings.section.account': 'Account',
  'settings.section.workspace': 'Workspace',
  'settings.overview.title': 'Settings overview',
  'settings.overview.description':
    'The current state of this account and workspace. Open a section for detail.',
  'settings.overview.open': 'Open',
  'settings.overview.notImplemented': 'Not implemented',
  'settings.overview.notReported': 'Not reported',
  'settings.demoOnly': 'Demo only - not saved',

  'settings.workspace.title': 'Workspace',
  'settings.workspace.description': 'The organization this account belongs to.',
  'settings.workspace.period.label': 'Default reporting period',
  'settings.workspace.period.hint':
    'Changes the period shown on this device only. It is not sent anywhere and does not survive a reload.',
  'settings.workspace.period.reset': 'Reset',
  'settings.workspace.preferences.unavailable':
    'Workspace preferences are not available. This product exposes no preferences service, so a saved choice could not be stored or applied.',

  /* ---------------------------------------------------------------- *
   * Preview navigator search                                          *
   * ---------------------------------------------------------------- */

  'contextBar.search.preview.label': 'Search sections',
  'contextBar.search.preview.placeholder': 'Jump to a section',
  'contextBar.search.preview.results': 'Matching sections',
  'contextBar.search.preview.noResults': 'No section matches that.',
  'contextBar.search.preview.scope':
    'Searches sections you can open. Document and report search needs a service this product does not have yet.',

} as const;

export type StringKey = keyof typeof en;
