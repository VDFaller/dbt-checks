{% docs order_status %}

The current lifecycle status for an order. The Jaffle Shop fixture uses
`completed`, `shipped`, and `returned` values.

{% enddocs %}

{% docs payment_amount %}

Payment amounts in the raw seed are stored as cents. The staging model converts
them to dollars before the marts aggregate payments.

{% enddocs %}
