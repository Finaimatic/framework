# icp_spec.template.yaml
#
# Abstract ICP spec for the Surveyor scoring agent.
# Copy this file, rename it per offer (e.g. icp_spec.<offer>.yaml), and fill in.
# Surveyor loads the filled copy as {icp_spec}. Never edit the agent — only specs.
#
# Field rules:
#   primary_signals    weighted high; direct predictors of need/buy/benefit
#   secondary_signals  supportive context; never decisive on their own
#   hard_disqualifiers absolute gates — tripping any one caps fit_score at 2
#   value_blockers     soft penalties — company resembles ICP but won't buy/benefit
#   anchors            offer-specific overrides of Surveyor's default 1-10 scale
#
# Keep signals observable from scraped content. If a human couldn't verify it
# from a website/profile, it doesn't belong here.


primary_signals:
  - <strongest buying signal: the thing that means they NEED this offer>
  - <evidence they have the budget / business model to pay>
  - <evidence of the right size / stage / decision-maker access>
  - <evidence the problem the offer solves is live for them>

secondary_signals:
  - <supporting context that raises confidence but isn't decisive>
  - <maturity / growth / recency signal>

hard_disqualifiers:        # absolute — cap fit_score at 2
  - <wrong category entirely>
  - <already has the capability this offer provides>
  - <too large / wrong stage to buy this way>
  - <structural mismatch (industry, geography, model)>

value_blockers:            # soft penalty — looks like ICP, won't convert
  - <already using a competing solution / partner>
  - <demand-saturated: not taking new clients, waitlisted>

anchors:                   # optional; omit to use Surveyor defaults
  "10":  <explicit, unambiguous perfect-fit description>
  "7-9": <clear strong fit, primary signals present, no blocker>
  "4-6": <mixed: some signals but key dimension unclear>
  "1-3": <wrong fit, or disqualified, or won't benefit>