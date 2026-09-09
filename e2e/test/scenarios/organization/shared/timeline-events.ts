const { H } = cy;
import { SAMPLE_DATABASE } from "e2e/support/cypress_sample_database";

const { ORDERS, ORDERS_ID } = SAMPLE_DATABASE;

export function createQuestionAndDashboardWithEvents() {
  interceptTimelineRequests();

  H.createTimelineWithEvents({
    timeline: { name: "Releases" },
    events: [{ name: "RC1", timestamp: "2027-10-20T00:00:00Z" }],
  })
    .then(({ timeline }) =>
      H.createQuestionAndDashboard({
        questionDetails: {
          name: "Orders by month",
          display: "line",
          query: {
            "source-table": ORDERS_ID,
            aggregation: [["count"]],
            breakout: [
              ["field", ORDERS.CREATED_AT, { "temporal-unit": "month" }],
            ],
          },
          visualization_settings: {
            "timeline.selected_timeline_ids": [timeline.id],
            "timeline.excluded_timeline_event_ids": [],
          },
          enable_embedding: true,
        },
        dashboardDetails: {
          name: "Dashboard with events",
          enable_embedding: true,
        },
      }),
    )
    .then(({ body: { dashboard_id }, questionId }) => {
      cy.wrap(questionId).as("questionId");
      cy.wrap(dashboard_id).as("dashboardId");
    });
}

export function interceptTimelineRequests(requestAlias = "timelineRequests") {
  cy.intercept(/\/api\/(?:timeline|timeline-event)(?:\/|\?|$)/).as(
    requestAlias,
  );
}

export function expectChartWithoutEvents({
  requestAlias = "timelineRequests",
  isInteractive = true,
} = {}) {
  H.echartsContainer().findByText("Created At: Month").should("be.visible");
  cy.findByTestId("timeline-event-chip").should("not.exist");
  if (isInteractive) {
    H.echartsContainer().trigger("mousemove", "bottom");
  }
  cy.findByTestId("timeline-event-popover").should("not.exist");
  cy.findByLabelText("Timeline event card").should("not.exist");
  cy.findByRole("button", { name: "Events", exact: true }).should("not.exist");
  cy.findByRole("menuitem", { name: "Events", exact: true }).should(
    "not.exist",
  );
  cy.findByRole("button", { name: "New event" }).should("not.exist");
  cy.icon("calendar").should("not.exist");
  cy.get(`@${requestAlias}.all`).should("have.length", 0);
}
