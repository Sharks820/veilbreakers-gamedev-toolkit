// TRUTH: CS-COR-06 on line 3
using System.Threading.Tasks;
public class Bad {
    public int Run(Task<int> work) { return work.Result; }
}
