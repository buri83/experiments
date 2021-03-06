import psycopg2
from psycopg2.extras import DictCursor
import time
import random
from concurrent.futures import ThreadPoolExecutor
import uuid

postgres_url = "postgresql://{username}:{password}@{hostname}:{port}/{database}".format(
    username="postgres",
    password="password",
    hostname="postgres",
    port=5432,
    database="postgres"
)

# Setting
EXPECTED_SUCCESS = 100
VISITING_USERS = 2000
VISITING_DURATION_SECS = 10


success_count = 0
failure_count = 0
times = []

def reset_counts():
    global success_count, failure_count, times
    success_count = 0
    failure_count = 0
    times = []

def execute_query(sql, params=None):
    db_latency_ms = 20

    results = None
    with psycopg2.connect(postgres_url) as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            time.sleep(db_latency_ms / 1000 / 2)
            cur.execute(sql, params)
            try:
                results = [dict(r) for r in cur.fetchall()]
            except:
                pass
            time.sleep(db_latency_ms / 1000 / 2)
    return results

def test0():
    global success_count, failure_count
    count = execute_query("""
        SELECT inventories FROM "Products" WHERE id = 0;
    """)[0]["inventories"]

    if count <= EXPECTED_SUCCESS:
        execute_query("""
            BEGIN;

            UPDATE "Products" SET inventories = inventories + 1
            WHERE id = 0;

            INSERT INTO "PurchasedItems" (id, product_id, user_name)
            VALUES
                (gen_random_uuid(), 0, 'test-user');

            COMMIT;
        """)
        success_count += 1
    else:
        failure_count += 1

def test1():
    global success_count, failure_count

    try:
        execute_query("""
            BEGIN;

            UPDATE "Products" SET inventories = inventories - 1
            WHERE id = 1;

            INSERT INTO "PurchasedItems" (id, product_id, user_name)
            VALUES (gen_random_uuid(), 1, 'test-user');

            COMMIT;
        """)
        success_count += 1
    except:
        failure_count += 1


def test2():
    global success_count, failure_count
    item_id = uuid.uuid4()

    execute_query("""
            BEGIN;

            INSERT INTO "PurchasedItems" (id, product_id, user_name)
            SELECT '{item_id}', 2, 'test-user'
            FROM "Products"
            WHERE id = 2 AND inventories < {max};

            UPDATE "Products" SET inventories = inventories + 1
            WHERE id = 2 AND inventories < {max};

            COMMIT;
        """.format(item_id=item_id, max=EXPECTED_SUCCESS))

    success = execute_query("""
        SELECT EXISTS (SELECT 1 FROM "PurchasedItems" WHERE id = '{}') AS result;
    """.format(item_id))[0]["result"]

    if success:
        success_count += 1
    else:
        failure_count += 1

def test3():
    global success_count, failure_count
    count = execute_query("""
        SELECT inventories FROM "Products" WHERE id = 3;
    """)[0]["inventories"]

    if count <= EXPECTED_SUCCESS:
        execute_query("""
            BEGIN;

            UPDATE "Products" SET inventories = {} + 1
            WHERE id = 3;

            INSERT INTO "PurchasedItems" (id, product_id, user_name)
            VALUES
                (gen_random_uuid(), 3, 'test-user');

            COMMIT;
        """.format(count))
        success_count += 1
    else:
        failure_count += 1


def run_with_random_delay(fn):
    global times
    max_delay_s = VISITING_DURATION_SECS

    time.sleep(random.random() * max_delay_s)

    st = time.time()
    fn()
    times.append(time.time() - st)


def start_test(fn):
    with ThreadPoolExecutor(max_workers=VISITING_USERS) as tpe:
        for i in range(VISITING_USERS):
            tpe.submit(run_with_random_delay, fn)
        tpe.shutdown()


"""
    # ??????
    ??????10????????????2000??????????????????????????????????????????
    ?????????1000???????????????????????????

    ?????????DB????????????20ms???????????????????????????????????????
"""

print("----------------------------\n")

# Test 0: 
# ??????????????????????????????????????????????????????????????????????????????100????????????????????????????????????
# ????????????????????????????????????????????? 1 ????????????????????????????????????
# ???????????????: ??????????????????????????????100??????????????????????????????????????????
"""
    --> ?????????????????????????????????DB????????????????????????????????????????????????????????????
    ?????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    ???????????????????????????????????????????????????????????????
"""
reset_counts()
start_test(test0)

print("Test 0")
print("succeeded = %s" % success_count)
print("failed = %s" % failure_count)
print("average_time = %s" % (sum(times) / len(times)))
print("----------------------------\n")


# Test 1: 
# ????????????????????????????????????????????????1??????????????????????????????
# Check constraint ??? 0????????????????????????????????????????????????????????? exception ??????????????????
# ???????????????: Exception ????????????????????????
"""
    --> ??????????????????
"""

reset_counts()
execute_query("""
    UPDATE "Products" SET inventories = {} WHERE id = 1;
""".format(EXPECTED_SUCCESS))

start_test(test1)

print("Test 1")
print("succeeded = %s" % success_count)
print("failed = %s" % failure_count)
print("average_time = %s" % (sum(times) / len(times)))
print("----------------------------\n")


# Test 2:
# ???????????????????????????????????????????????????????????????????????????????????????1????????????????????????????????????ID ???????????????????????????????????????????????????
# ???????????????: ID ??????????????????????????????????????????
"""
    --> ???????????????????????????????????????????????????????????????????????? read committed ???????????????????????????????????????non-repeatable read ???????????????????????????
    ?????????user???10k?????????????????????
"""
reset_counts()
start_test(test2)

print("Test 2")
print("succeeded = %s" % success_count)
print("failed = %s" % failure_count)
print("average_time = %s" % (sum(times) / len(times)))
print("----------------------------\n")


# Test 3: 
# ??????????????????????????????????????????????????????????????????????????????100????????????????????????????????????
# ????????????????????????????????????????????????count + 1 ???????????????????????????????????????
# ???????????????: ??????????????????????????????100??????????????????????????????????????????
"""
    --> ?????????????????????????????????????????????????????????
"""
reset_counts()
start_test(test3)

print("Test 3")
print("succeeded = %s" % success_count)
print("failed = %s" % failure_count)
print("average_time = %s" % (sum(times) / len(times)))
print("----------------------------\n")
