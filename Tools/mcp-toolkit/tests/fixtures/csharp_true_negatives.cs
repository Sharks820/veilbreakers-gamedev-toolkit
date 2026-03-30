using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;

// This file contains GOOD CODE that must NOT be flagged.
// Each pattern is specifically designed to test that a rule does NOT fire.

public class GoodCode : MonoBehaviour
{
    // Cached component -- NOT BUG-01
    private Rigidbody _rb;
    private Camera _mainCam;

    void Awake()
    {
        // GetComponent in Awake is correct -- NOT BUG-01
        _rb = GetComponent<Rigidbody>();
        // Camera.main in Awake -- NOT BUG-02
        _mainCam = Camera.main;
    }

    void Start()
    {
        // GetComponent in Start is correct -- NOT BUG-01
        var col = GetComponent<Collider>();
    }

    void Update()
    {
        // Using cached reference -- NOT BUG-01, NOT BUG-02
        _rb.velocity = Vector3.zero;
        var camPos = _mainCam.transform.position;
    }

    // async Task is correct -- NOT BUG-11
    async Task DoWorkAsync()
    {
        await Task.Delay(1);
    }

    // async void for event handler is correct -- NOT BUG-11
    async void OnButtonClicked()
    {
        await Task.Delay(1);
    }

    // Non-empty lifecycle method -- NOT BUG-18
    void LateUpdate()
    {
        // Some actual work
        _rb.velocity = Vector3.zero;
    }

    // VB-IGNORE suppression -- NOT BUG-20
    void DebugSafe()
    {
        Debug.Log("safe"); // VB-IGNORE
    }

    // CompareTag instead of == -- NOT BUG-26
    void TagCheckGood(GameObject go)
    {
        if (go.CompareTag("Player")) { }
    }

    // yield return null instead of 0 -- NOT BUG-35
    IEnumerator GoodCoroutine()
    {
        yield return null;
    }

    // DontDestroyOnLoad(gameObject) -- NOT BUG-40
    void MakePersistentGood()
    {
        DontDestroyOnLoad(gameObject);
    }

    // Correct position assignment -- NOT BUG-44
    void MoveXGood()
    {
        var pos = transform.position;
        pos.x = 5f;
        transform.position = pos;
    }

    // while(true) with yield -- NOT BUG-49
    IEnumerator GoodLoop()
    {
        while (true) {
            yield return null;
        }
    }

    // Coroutine without string -- NOT BUG-41
    void StartGood()
    {
        StartCoroutine(GoodCoroutine());
    }

    // Exception handler with logging -- NOT QUAL-06
    void CatchGood()
    {
        try { int x = 1; } catch (System.Exception e) { Debug.LogError(e); }
    }

    // HTTPS URL -- NOT SEC-05
    void FetchSecure()
    {
        var url = "https://example.com/data";
    }

    // Code inside #if UNITY_EDITOR block -- NOT UNITY-09
#if UNITY_EDITOR
    void EditorOnly()
    {
        UnityEditor.EditorApplication.isPlaying = false;
    }
#endif

    // GetComponent in cold path with null check -- should not flag BUG-09
    void ColdPathGetComponent()
    {
        var rb = GetComponent<Rigidbody>();
        if (rb != null) { rb.velocity = Vector3.zero; }
    }

    // String in code that looks like a bug but is in a string literal
    void StringLiteral()
    {
        string msg = "GetComponent<Rigidbody>() should be called in Awake";
    }

    // Comment that looks like a bug
    // GetComponent<Rigidbody>() in Update is bad

    // foreach in cold path -- NOT BUG-19
    void ColdPath()
    {
        var items = new List<int> { 1, 2, 3 };
        foreach (var x in items) { }
    }
}
