const { H } = cy;

import {
  createQuestionAndDashboardWithEvents,
  expectChartWithoutEvents,
  interceptTimelineRequests,
} from "./shared/timeline-events";

describe("scenarios > organization > timelines > public links and embeds", () => {
  beforeEach(() => {
    H.restore();
    cy.signInAsAdmin();
    createQuestionAndDashboardWithEvents();
  });

  it("should not show events on a public question", () => {
    cy.get<number>("@questionId").then((id) => H.visitPublicQuestion(id));

    expectChartWithoutEvents();
  });

  it("should not show events on a static embedded question", () => {
    cy.get<number>("@questionId").then((id) =>
      H.visitEmbeddedPage({ resource: { question: id }, params: {} }),
    );

    expectChartWithoutEvents();
  });

  it("should not show events on a public dashboard", () => {
    cy.get<number>("@dashboardId").then((id) => H.visitPublicDashboard(id));

    expectChartWithoutEvents();
    expectDashboardMenuWithoutEvents();
  });

  it("should not show events on a static embedded dashboard", () => {
    cy.get<number>("@dashboardId").then((id) =>
      H.visitEmbeddedPage({ resource: { dashboard: id }, params: {} }),
    );

    expectChartWithoutEvents();
    expectDashboardMenuWithoutEvents();
  });

  it("should not show events on a public document", () => {
    cy.get<number>("@questionId").then((id) => {
      H.createDocument({
        name: "Document with events",
        document: {
          type: "doc",
          content: [
            {
              type: "resizeNode",
              attrs: { height: 400, minHeight: 280 },
              content: [
                { type: "cardEmbed", attrs: { id, name: null, _id: "1" } },
              ],
            },
          ],
        },
        idAlias: "documentId",
      });
    });
    H.visitPublicDocument("@documentId");

    expectChartWithoutEvents();
  });

  (["question", "dashboard"] as const).forEach((resource) => {
    it(`should not show events or request timelines in a ${resource} embed preview`, () => {
      cy.get<number>(`@${resource}Id`).then((id) => {
        if (resource === "question") {
          H.visitQuestion(id);
        } else {
          H.visitDashboard(id);
        }
        H.timelineEventChip("RC1").should("be.visible");

        interceptTimelineRequests("previewTimelineRequests");
        cy.intercept(
          "GET",
          resource === "question"
            ? "/api/preview_embed/card/*/query*"
            : "/api/preview_embed/dashboard/*/dashcard/*/card/*",
        ).as("previewQuery");
        H.openLegacyStaticEmbeddingModal({
          resource,
          resourceId: id,
          activeTab: "parameters",
          previewMode: "preview",
          unpublishBeforeOpen: false,
        });
      });

      cy.wait("@previewQuery");
      H.getIframeBody().within(() => {
        expectChartWithoutEvents({ requestAlias: "previewTimelineRequests" });
        if (resource === "dashboard") {
          expectDashboardMenuWithoutEvents("previewTimelineRequests");
        }
      });
    });
  });
});

describe("scenarios > organization > timelines > full-app embedding", () => {
  beforeEach(() => {
    H.restore();
    cy.signInAsAdmin();
    H.activateToken("pro-self-hosted");
    createQuestionAndDashboardWithEvents();
  });

  it("should keep events unavailable when navigating between an embedded dashboard and question", () => {
    cy.get<number>("@dashboardId").then((id) => {
      H.visitFullAppEmbeddingUrl({ url: `/dashboard/${id}` });
    });
    expectChartWithoutEvents();

    H.dashboardHeader()
      .findByRole("button", { name: "Move, trash, and more…" })
      .click();
    H.menu().should("be.visible").findByText("Events").should("not.exist");
    cy.realPress("Escape");
    expectDashboardMenuWithoutEvents();

    H.getDashboardCard()
      .findByRole("link", { name: "Orders by month" })
      .click();
    cy.location("pathname").should("match", /\/question\/\d+/);
    expectChartWithoutEvents();

    cy.go("back");
    cy.location("pathname").should("match", /\/dashboard\/\d+/);
    expectChartWithoutEvents();
  });
});

function expectDashboardMenuWithoutEvents(requestAlias = "timelineRequests") {
  H.getDashboardCard().realHover();
  H.getDashboardCard().findByRole("button", { name: "More options" }).click();
  H.menu().should("be.visible").findByText("Events").should("not.exist");
  cy.realPress("Escape");
  cy.get(`@${requestAlias}.all`).should("have.length", 0);
}
