(ns metabase.queries.card-schema
  "The `:model/Card` columns that have to be SELECTed together for the `:card_schema` upgrade to run, plus the
  helpers that project them.

  This namespace is deliberately tiny. `metabase.queries.core` pulls in most of the `queries` module, and the
  low-level `db.clj` namespaces that need these helpers sit *below* it in the load graph — requiring the module's
  main API namespace from them is a cyclic load. Nothing here needs more than Toucan."
  (:require
   [toucan2.core :as t2]))

(def schema-governed-columns
  "The columns of `:model/Card` whose stored representation is relevant to `:card_schema`. These columns must be
  read together, and will be written back together.

  Keep this in sync when adding an upgrade that rewrites a new column."
  #{:dataset_query :result_metadata :dimensions :dimension_mappings})

(def schema-upgrade-triggers
  "All the columns which any [[metabase.queries.models.card/upgrade-card-schema-to]] function reads, implying that
  they can impact a card at read time. A SELECT of any [[schema-governed-columns]] must include all of these.

  `:card_schema` belongs here rather than in [[schema-governed-columns]]: it is the version marker, not a governed
  representation, so selecting it alone (to satisfy this very rule) must not itself demand the rest of the set.

  Keep this in sync with the columns read by the `upgrade-card-schema-to` implementations."
  (conj schema-governed-columns :card_schema :type :database_id))

(def ^:private schema-select-columns
  "The `[modelable & columns]` projection [[card-by-id]] and [[cards-by-id]] SELECT with: `:id` (without it the
  upgrade never runs at all) plus every [[schema-upgrade-triggers]] column."
  (into [:id] schema-upgrade-triggers))

(defn- projection [include]
  (into [:model/Card] (concat schema-select-columns include)))

(defn card-by-id
  "The Card with `card-id`, or nil.

  Projects every column the `:card_schema` upgrade needs, so the Card comes back upgraded to the current schema
  version rather than tripping the \"without all columns needed for an upgrade\" error. Prefer this over a
  hand-written projection whenever a caller wants a Card's `:dataset_query`, `:result_metadata`, `:dimensions` or
  `:dimension_mappings` by id.

  `:include` *augments* the projection with additional columns; it never replaces it."
  [card-id & {:keys [include]}]
  (t2/select-one (projection include) :id card-id))

(defn cards-by-id
  "The Cards with `card-ids`, in no particular order.

  Projects the same columns as [[card-by-id]], and `:include` augments them the same way. Callers wanting a lookup
  table should `u/index-by :id` the result."
  [card-ids & {:keys [include]}]
  (when (seq card-ids)
    (t2/select (projection include) :id [:in card-ids])))
