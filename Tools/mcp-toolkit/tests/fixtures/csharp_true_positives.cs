using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Linq;

// This file contains code that MUST trigger specific rules.
// Each method tests one or more rule IDs.

public class BuggyCode : MonoBehaviour
{
    // === HOT PATH BUGS (inside Update) ===

    void Update()
    {
        // BUG-01: GetComponent in Update
        var rb = GetComponent<Rigidbody>();

        // BUG-02: Camera.main in Update
        var pos = Camera.main.transform.position;

        // BUG-03: FindObjectOfType in Update
        var enemy = FindObjectOfType<Enemy>();

        // BUG-04: Heap allocation in Update
        var items = new List<int>();

        // BUG-06: GameObject.Find in Update
        var player = GameObject.Find("Player");

        // BUG-19: foreach in hot path (semantic layer)
        foreach (var x in items) { }

        // BUG-28: LINQ in Update
        var first = items.Where(x => x > 0).ToList();

        // BUG-32: GetComponentInChildren in Update
        var child = GetComponentInChildren<Collider>();

        // BUG-33: FindWithTag in Update
        var tagged = GameObject.FindWithTag("Enemy");

        // PERF-27: Transform.Find in hot path
        var foot = transform.Find("LeftFoot");

        // PERF-19: SetActive in hot path
        gameObject.SetActive(true);
    }

    // === ASYNC BUGS ===

    // BUG-11: async void method (not an event handler)
    async void DoWork()
    {
        await Task.Delay(1);
    }

    // === COLLISION / QUALITY ===

    // BUG-15: Collision callback detected (semantic layer)
    void OnCollisionEnter(Collision c) { }

    // === UNITY LIFECYCLE ===

    // BUG-18: Empty lifecycle method
    void LateUpdate() { }

    // BUG-20: Debug.Log in production
    void SomeMethod()
    {
        Debug.Log("hello");
    }

    // BUG-26: Comparing tag with ==
    void TagCheck(GameObject go)
    {
        if (go.tag == "Player") { }
    }

    // BUG-35: yield return 0 (boxing)
    IEnumerator MyCoroutine()
    {
        yield return 0;
    }

    // BUG-40: DontDestroyOnLoad(this)
    void MakePersistent()
    {
        DontDestroyOnLoad(this);
    }

    // BUG-44: Assigning to transform.position.x (struct copy)
    void MoveX()
    {
        transform.position.x = 5f;
    }

    // BUG-49: Infinite while(true) without yield/break
    IEnumerator InfiniteLoop()
    {
        while (true) {
            DoSomething();
        }
    }

    // UNITY-06: Invoke with string
    void StartDelayed()
    {
        Invoke("DoWork", 1.0f);
    }

    // UNITY-18: SendMessage
    void NotifyAll()
    {
        SendMessage("OnDamage");
    }

    // QUAL-06: Empty catch block
    void CatchNothing()
    {
        try { int x = 1; } catch (System.Exception e) { }
    }

    // QUAL-07: TODO comment
    // TODO fix this later

    // BUILD-01: using UnityEditor outside #if UNITY_EDITOR
    // (this is a file-level rule, tested separately below)

    // SEC-05: HTTP URL
    void FetchData()
    {
        var url = "http://example.com/data";
    }

    // SAVE-01: BinaryFormatter
    void SaveGame()
    {
        var bf = new BinaryFormatter();
    }

    // THREAD-01: Task.Run in Unity
    void RunBackground()
    {
        Task.Run(() => { });
    }

    // BUG-41: StartCoroutine with string
    void StartByName()
    {
        StartCoroutine("MyCoroutine");
    }

    void DoSomething() { }
}
